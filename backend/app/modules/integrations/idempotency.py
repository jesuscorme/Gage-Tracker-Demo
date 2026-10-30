"""Idempotent writes for integrations.

A client may send ``Idempotency-Key: <unique value>`` on POST/PUT/PATCH. The first
request is executed and its response stored; a retry with the same key and the same
request returns the stored response (``Idempotent-Replayed: true``) without executing
the operation again. Reusing a key for a different request is rejected, and a retry
while the first request is still running gets 409. Keys are scoped to the caller's
credential and organization header, and kept for 24 hours.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.db import get_db
from app.modules.integrations.models import IdempotencyRecord

HEADER = "Idempotency-Key"
METHODS = {"POST", "PUT", "PATCH"}
RETENTION = timedelta(hours=24)


def _error(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {
        "code": code, "message": message, "details": None, "request_id": getattr(request.state, "request_id", None)}})


class _Session:
    """Use the application's session provider (honours test dependency overrides)."""

    def __init__(self, app):
        provider = app.dependency_overrides.get(get_db, get_db)
        self._gen = provider()
        self.db = next(self._gen) if hasattr(self._gen, "__next__") else self._gen

    def close(self):
        if hasattr(self._gen, "close"):
            self._gen.close()


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = request.headers.get(HEADER)
        if not key or request.method not in METHODS or not request.url.path.startswith("/api/v1/"):
            return await call_next(request)
        credential = request.headers.get("authorization") or request.headers.get("x-api-key")
        if not credential:
            return await call_next(request)          # unauthenticated calls fail in the endpoint anyway
        if len(key) > 100 or not key.strip():
            return _error(request, 422, "invalid_idempotency_key", "Idempotency-Key must be 1-100 characters")
        body = await request.body()
        scope = hashlib.sha256(f"{credential}|{request.headers.get('x-organization-id', '')}".encode()).hexdigest()
        req_hash = hashlib.sha256(request.method.encode() + request.url.path.encode() + b"|" + body).hexdigest()
        session = _Session(request.app)
        try:
            claim = await run_in_threadpool(self._claim, session.db, scope, key, request, req_hash)
            if isinstance(claim, Response):
                return claim
            response = await call_next(request)
            chunks = [c async for c in response.body_iterator]
            payload = b"".join(chunks)
            await run_in_threadpool(self._store, session.db, claim, response.status_code, payload,
                                    response.headers.get("content-type"))
            headers = dict(response.headers)
            headers.pop("content-length", None)
            return Response(content=payload, status_code=response.status_code, headers=headers,
                            media_type=response.media_type)
        finally:
            session.close()

    @staticmethod
    def _claim(db, scope, key, request: Request, req_hash):
        db.execute(delete(IdempotencyRecord).where(IdempotencyRecord.created_at < datetime.now(UTC) - RETENTION))
        existing = db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.scope_hash == scope,
                                                             IdempotencyRecord.idempotency_key == key))
        if existing is not None:
            db.commit()
            if existing.request_hash != req_hash:
                return _error(request, 422, "idempotency_key_reused",
                              "This Idempotency-Key was used for a different request")
            if existing.status_code is None:
                return _error(request, 409, "idempotency_in_progress",
                              "A request with this Idempotency-Key is still being processed")
            return Response(content=(existing.response_body or "").encode(), status_code=existing.status_code,
                            media_type=existing.content_type or "application/json",
                            headers={"Idempotent-Replayed": "true"})
        record = IdempotencyRecord(scope_hash=scope, idempotency_key=key, method=request.method,
                                   path=request.url.path[:300], request_hash=req_hash)
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return _error(request, 409, "idempotency_in_progress",
                          "A request with this Idempotency-Key is still being processed")
        return record.id

    @staticmethod
    def _store(db, record_id, status, payload: bytes, content_type):
        record = db.get(IdempotencyRecord, record_id)
        if record is None:
            return
        if status >= 500:
            db.delete(record)                      # a server error may be retried
        else:
            record.status_code = status
            try:
                record.response_body = payload.decode("utf-8")
            except UnicodeDecodeError:
                record.response_body = json.dumps({"note": "binary response not stored"})
            record.content_type = content_type
        db.commit()
