from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live():
    """The process is up."""
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    """The API can serve traffic: database reachable and migrated."""
    try:
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "error"})
    return {"status": "ok", "database": "ok", "schema_revision": revision}
