import logging
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.analytics.router import router as analytics_router
from app.auth.router import router as auth_router
from app.automation.router import router as automation_router
from app.config import get_settings
from app.database import mongo
from app.logging_setup import configure_logging, request_id_var
from app.notifications.router import router as notifications_router
from app.privacy.router import audit_router
from app.privacy.router import router as privacy_router
from app.profiles.router import router as profile_router
from app.resumes.router import router as resumes_router
from app.utils import new_id

logger = logging.getLogger("saige.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    owns_connection = not mongo.is_connected()
    if owns_connection:
        mongo.connect(settings.mongodb_uri, settings.mongodb_db)
    await mongo.ensure_indexes(mongo.get_db())
    logger.info("Saige AI API started")
    yield
    if owns_connection:
        mongo.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Saige AI API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/api/docs",
        openapi_url=None if settings.is_production else "/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or new_id()
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error")
            response = JSONResponse({"detail": "Internal server error", "request_id": rid},
                                    status_code=500)
        duration = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        logger.info("request", extra={"method": request.method, "path": request.url.path,
                                      "status": response.status_code, "duration_ms": duration})
        request_id_var.reset(token)
        return response

    api = APIRouter(prefix="/api")

    @api.get("/health", tags=["system"])
    async def health():
        try:
            await mongo.get_db().command("ping")
            db_ok = True
        except Exception:  # noqa: BLE001 - health must never raise
            db_ok = False
        return {"status": "ok" if db_ok else "degraded", "database": db_ok}

    for r in (auth_router, profile_router, resumes_router, analytics_router, automation_router,
              notifications_router, privacy_router, audit_router):
        api.include_router(r)
    app.include_router(api)
    return app


app = create_app()
