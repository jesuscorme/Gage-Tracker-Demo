"""Webhook delivery of outbox events: fan-out, HMAC signature, retries with backoff.

Every delivery has a stable id (``X-GageTracker-Delivery``) so receivers can discard
duplicates; one delivery exists per (endpoint, event), so an event is never queued
twice for the same endpoint. The body is signed with the endpoint secret:
``X-GageTracker-Signature: sha256=HMAC_SHA256(secret, "<timestamp>.<body>")``.
"""

import hashlib
import hmac
import ipaddress
import json
import secrets
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.modules.events.models import EVENT_TYPES, OutboxEvent
from app.modules.identity.deps import TenantContext
from app.modules.integrations.models import WebhookAttempt, WebhookDelivery, WebhookEndpoint

# Delay before attempt n+1 after a failed attempt n.
BACKOFF = [timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30), timedelta(hours=2),
           timedelta(hours=12)]
MAX_ATTEMPTS = len(BACKOFF) + 1

Sender = Callable[[str, dict, bytes], int]


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    settings = get_settings()
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise BusinessRuleError("The webhook URL must be an absolute http(s) URL", code="invalid_url")
    if parsed.scheme == "http" and (settings.app_env == "production" or not settings.webhook_allow_http):
        raise BusinessRuleError("Webhook URLs must use https", code="invalid_url")
    if settings.app_env == "production":
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise BusinessRuleError("Private network addresses are not allowed", code="invalid_url")
        except ValueError:
            if parsed.hostname in ("localhost",):
                raise BusinessRuleError("Private network addresses are not allowed", code="invalid_url")


def create_endpoint(ctx: TenantContext, name: str, url: str, event_types: list[str]) -> tuple[WebhookEndpoint, str]:
    _validate_url(url)
    bad = [e for e in event_types if e not in EVENT_TYPES]
    if bad or not event_types:
        raise BusinessRuleError("Unknown event types", code="invalid_event_types",
                                details={"unknown": bad, "available": list(EVENT_TYPES)})
    secret = "whsec_" + secrets.token_urlsafe(24)
    ep = WebhookEndpoint(organization_id=ctx.organization_id, name=name, url=url, secret=secret,
                         event_types=sorted(set(event_types)), created_by=ctx.user_id)
    ctx.db.add(ep)
    ctx.db.flush()
    ctx.audit(action="webhook.created", entity_type="webhook_endpoint", entity_id=ep.id,
              changes={"name": name, "url": url, "event_types": ep.event_types})
    ctx.db.commit()
    return ep, secret


def get_endpoint(ctx: TenantContext, endpoint_id: uuid.UUID) -> WebhookEndpoint:
    ep = ctx.db.scalar(select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id,
                                                     WebhookEndpoint.organization_id == ctx.organization_id))
    if ep is None:
        raise NotFoundError("Webhook endpoint not found")
    return ep


def set_active(ctx: TenantContext, endpoint_id: uuid.UUID, active: bool) -> WebhookEndpoint:
    ep = get_endpoint(ctx, endpoint_id)
    ep.is_active = active
    ctx.audit(action="webhook.activated" if active else "webhook.deactivated", entity_type="webhook_endpoint",
              entity_id=ep.id, changes={"is_active": active})
    ctx.db.commit()
    return ep


def list_endpoints(ctx: TenantContext) -> list[WebhookEndpoint]:
    return list(ctx.db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.organization_id == ctx.organization_id)
                               .order_by(WebhookEndpoint.created_at)))


def deliveries(ctx: TenantContext, endpoint_id: uuid.UUID | None, status: str | None, limit: int):
    stmt = (select(WebhookDelivery, OutboxEvent.event_type, OutboxEvent.entity_id)
            .join(OutboxEvent, OutboxEvent.id == WebhookDelivery.event_id)
            .where(WebhookDelivery.organization_id == ctx.organization_id))
    if endpoint_id:
        stmt = stmt.where(WebhookDelivery.endpoint_id == endpoint_id)
    if status:
        stmt = stmt.where(WebhookDelivery.status == status)
    return ctx.db.execute(stmt.order_by(WebhookDelivery.created_at.desc()).limit(limit)).all()


def attempts(ctx: TenantContext, delivery_id: uuid.UUID) -> list[WebhookAttempt]:
    d = ctx.db.scalar(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id,
                                                    WebhookDelivery.organization_id == ctx.organization_id))
    if d is None:
        raise NotFoundError("Delivery not found")
    return list(ctx.db.scalars(select(WebhookAttempt).where(WebhookAttempt.delivery_id == d.id)
                               .order_by(WebhookAttempt.attempt)))


def retry(ctx: TenantContext, delivery_id: uuid.UUID) -> WebhookDelivery:
    d = ctx.db.scalar(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id,
                                                    WebhookDelivery.organization_id == ctx.organization_id))
    if d is None:
        raise NotFoundError("Delivery not found")
    if d.status == "SUCCEEDED":
        raise ConflictError("The delivery already succeeded", code="invalid_status")
    d.status, d.next_attempt_at = "PENDING", datetime.now(UTC)
    ctx.audit(action="webhook.delivery_retried", entity_type="webhook_delivery", entity_id=d.id,
              changes={"attempts": d.attempts})
    ctx.db.commit()
    return d


# ---------------------------------------------------------------- background processing

def enqueue(db: Session, organization_id: uuid.UUID | None = None) -> int:
    """Create deliveries for events published after each endpoint was created."""
    stmt = (select(OutboxEvent.id, WebhookEndpoint.id, OutboxEvent.organization_id)
            .join(WebhookEndpoint, and_(WebhookEndpoint.organization_id == OutboxEvent.organization_id,
                                        WebhookEndpoint.is_active.is_(True),
                                        OutboxEvent.created_at >= WebhookEndpoint.created_at,
                                        WebhookEndpoint.event_types.contains(
                                            func.jsonb_build_array(OutboxEvent.event_type))))
            .outerjoin(WebhookDelivery, and_(WebhookDelivery.event_id == OutboxEvent.id,
                                             WebhookDelivery.endpoint_id == WebhookEndpoint.id))
            .where(WebhookDelivery.id.is_(None)))
    if organization_id:
        stmt = stmt.where(OutboxEvent.organization_id == organization_id)
    rows = db.execute(stmt.limit(1000)).all()
    now = datetime.now(UTC)
    for event_id, endpoint_id, org_id in rows:
        db.execute(insert(WebhookDelivery).values(
            id=uuid.uuid4(), organization_id=org_id, endpoint_id=endpoint_id, event_id=event_id, status="PENDING",
            attempts=0, next_attempt_at=now).on_conflict_do_nothing(index_elements=["endpoint_id", "event_id"]))
    db.commit()
    return len(rows)


def http_sender(url: str, headers: dict, body: bytes) -> int:
    with httpx.Client(timeout=get_settings().webhook_timeout_seconds, follow_redirects=False) as client:
        return client.post(url, content=body, headers=headers).status_code


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def dispatch(db: Session, sender: Sender = http_sender, now: datetime | None = None,
             organization_id: uuid.UUID | None = None, limit: int = 50) -> dict:
    now = now or datetime.now(UTC)
    stmt = (select(WebhookDelivery).where(WebhookDelivery.status.in_(("PENDING", "FAILED")),
                                          WebhookDelivery.next_attempt_at <= now)
            .order_by(WebhookDelivery.next_attempt_at).limit(limit).with_for_update(skip_locked=True))
    if organization_id:
        stmt = stmt.where(WebhookDelivery.organization_id == organization_id)
    counts = {"succeeded": 0, "failed": 0, "dead": 0}
    for d in db.scalars(stmt).all():
        ep = db.get(WebhookEndpoint, d.endpoint_id)
        event = db.get(OutboxEvent, d.event_id)
        body = json.dumps(event.payload | {"event_id": str(event.id), "delivery_id": str(d.id)},
                          separators=(",", ":"), sort_keys=True).encode()
        ts = str(int(time.time()))
        headers = {"Content-Type": "application/json", "User-Agent": "GageTracker-Webhooks/1",
                   "X-GageTracker-Event": event.event_type, "X-GageTracker-Delivery": str(d.id),
                   "X-GageTracker-Timestamp": ts, "X-GageTracker-Signature": sign(ep.secret, ts, body)}
        started = time.monotonic()
        code, error = None, None
        try:
            code = sender(ep.url, headers, body)
        except Exception as exc:  # network errors are recorded, never raised
            error = f"{type(exc).__name__}: {exc}"[:500]
        d.attempts += 1
        db.add(WebhookAttempt(delivery_id=d.id, attempt=d.attempts, status_code=code, error=error,
                              duration_ms=int((time.monotonic() - started) * 1000)))
        d.last_status_code, d.last_error = code, error or (None if code and 200 <= code < 300 else f"HTTP {code}")
        if code is not None and 200 <= code < 300:
            d.status, d.delivered_at, d.next_attempt_at = "SUCCEEDED", now, None
            counts["succeeded"] += 1
        elif d.attempts >= MAX_ATTEMPTS:
            d.status, d.next_attempt_at = "DEAD", None
            counts["dead"] += 1
        else:
            d.status, d.next_attempt_at = "FAILED", now + BACKOFF[d.attempts - 1]
            counts["failed"] += 1
    db.commit()
    return counts
