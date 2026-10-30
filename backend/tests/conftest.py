"""Test fixtures.

The suite runs against a real PostgreSQL database (``TEST_DATABASE_URL``). At session
start the schema is dropped and rebuilt through the Alembic migrations (upgrade ->
downgrade to base -> upgrade), so every run proves the migrations work from a clean
database. Each test runs inside a transaction that is rolled back afterwards.
"""

import os
import uuid
from datetime import UTC, datetime

from dotenv import dotenv_values

_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
TEST_DB = os.environ.get("TEST_DATABASE_URL") or _env.get("TEST_DATABASE_URL")
if not TEST_DB:
    raise RuntimeError("TEST_DATABASE_URL is not configured")
os.environ["DATABASE_URL"] = TEST_DB
os.environ["APP_ENV"] = "test"
os.environ["LOG_JSON"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["BCRYPT_ROUNDS"] = "4"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.db import get_db  # noqa: E402
from app.main import create_app  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "Metrology-2026"


def alembic_config() -> Config:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    cfg.attributes["database_url"] = TEST_DB
    return cfg


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


def today():
    return datetime.now(UTC).date()


class Actor:
    """An authenticated user acting inside one organization."""

    def __init__(self, client: TestClient, token: str, org_id: str, plant_id: str | None = None):
        self.client = client
        self.token = token
        self.org_id = org_id
        self.plant_id = plant_id

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}", "X-Organization-Id": self.org_id}

    def get(self, url, **kw):
        return self.client.get(url, headers=self.headers, **kw)

    def post(self, url, json=None, **kw):
        return self.client.post(url, json=json, headers=self.headers, **kw)

    def patch(self, url, json=None, **kw):
        return self.client.patch(url, json=json, headers=self.headers, **kw)


@pytest.fixture()
def make_org(client):
    """Register a new organization; returns its administrator as an :class:`Actor`."""

    def _make(name: str = "Org") -> Actor:
        email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
        r = client.post("/api/v1/auth/register", json={
            "organization_name": name, "plant_code": "P1", "plant_name": f"{name} Plant 1",
            "timezone": "UTC", "full_name": f"{name} Admin", "email": email, "password": PASSWORD,
        })
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        org_id = me["memberships"][0]["organization_id"]
        actor = Actor(client, token, org_id)
        actor.plant_id = actor.get("/api/v1/plants").json()[0]["id"]
        actor.email = email
        return actor

    return _make


@pytest.fixture()
def add_user(client):
    """Create a user in the admin's organization with a role and log them in."""

    def _add(admin: Actor, role: str, plant_ids: list[str] | None = None) -> Actor:
        email = f"{role}-{uuid.uuid4().hex[:8]}@example.com"
        r = admin.post("/api/v1/users", json={
            "email": email, "full_name": f"{role} user", "password": PASSWORD,
            "role_code": role, "plant_ids": plant_ids or [],
        })
        assert r.status_code == 201, r.text
        token = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
        actor = Actor(client, token, admin.org_id, admin.plant_id)
        actor.user_id = r.json()["id"]
        return actor

    return _add


@pytest.fixture()
def gage_type(make_org):
    def _make(admin: Actor, code: str = "CAL", default_frequency_days: int | None = 365) -> dict:
        r = admin.post("/api/v1/gage-types", json={
            "code": code, "name": f"Type {code}", "default_frequency_days": default_frequency_days,
        })
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture()
def new_gage():
    def _make(actor: Actor, type_id: str, code: str = "G-001", **extra) -> dict:
        body = {"gage_code": code, "description": "Digital caliper 0-150 mm", "gage_type_id": type_id,
                "plant_id": actor.plant_id} | extra
        r = actor.post("/api/v1/gages", json=body)
        assert r.status_code == 201, r.text
        return r.json()

    return _make
