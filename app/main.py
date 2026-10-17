"""App factory: wires middleware, error handlers and routers into the FastAPI app.
Also serves /health, which checks the database connection."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.error_handlers import error_response, register_exception_handlers
from app.api.v1.tickets import router as tickets_router
from app.core.config import get_settings
from app.core.constants import (
    API_V1_PREFIX,
    APP_TITLE,
    APP_VERSION,
    HEALTH_OK,
    HEALTH_PATH,
    LOCATION_HEADER,
)
from app.core.exceptions import ErrorCode
from app.core.logging import setup_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestIdMiddleware
from app.db.session import get_db
from app.schemas.common import HealthResponse

logger = logging.getLogger(__name__)

health_router = APIRouter(tags=["health"])


# Return 200 if the database answers, 503 if it doesn't
@health_router.get(HEALTH_PATH, response_model=HealthResponse)
def health(db: Annotated[Session, Depends(get_db)]) -> HealthResponse | JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health check failed: database unreachable")
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ErrorCode.SERVICE_UNAVAILABLE,
            "Database is unreachable",
        )
    return HealthResponse(status=HEALTH_OK, database=HEALTH_OK)


# Build the app: logging, middleware, error handlers and routes
def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)

    app = FastAPI(title=APP_TITLE, version=APP_VERSION)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=[REQUEST_ID_HEADER, LOCATION_HEADER],
        )
    # added last = outermost, so CORS responses get a request id too
    app.add_middleware(RequestIdMiddleware)

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(tickets_router, prefix=API_V1_PREFIX)

    logger.info("Application created (env=%s)", settings.app_env)
    return app


app = create_app()
