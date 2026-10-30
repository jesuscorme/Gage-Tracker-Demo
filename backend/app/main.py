from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.modules.audit.router import router as audit_router
from app.modules.calibration.router import router as calibration_router
from app.modules.competency.router import router as competency_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.documents.router import router as documents_router
from app.modules.gages.router import router as gages_router
from app.modules.health.router import router as health_router
from app.modules.identity.router import auth_router, users_router
from app.modules.laboratory.router import router as laboratory_router
from app.modules.notifications.router import router as notifications_router
from app.modules.organizations.router import router as organizations_router
from app.modules.standards.router import router as standards_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        version="0.5.0",
        docs_url="/api/docs" if settings.app_env != "production" else None,
        openapi_url="/api/openapi.json" if settings.app_env != "production" else None,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Organization-Id", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    register_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    for r in (auth_router, users_router, organizations_router, audit_router, documents_router, gages_router,
              dashboard_router, standards_router, competency_router, calibration_router, laboratory_router,
              notifications_router):
        api.include_router(r)
    app.include_router(health_router)
    app.include_router(api)
    return app


app = create_app()
