import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from chatbot.adapters.persistence.postgres.orm import start_mappers
from chatbot.entrypoints.dependencies import shutdown_engine
from chatbot.entrypoints.error_handlers import ERROR_RESPONSES, install_error_handlers
from chatbot.entrypoints.logging_setup import RequestIdMiddleware, configure_logging
from chatbot.entrypoints.routers.auth import router as auth_router
from chatbot.entrypoints.routers.conversations import router as conversations_router
from chatbot.entrypoints.routers.limiter import limiter
from chatbot.entrypoints.settings import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Settings are checked here, not at import (BLUEPRINT D4): importing the app
    # (unit tests, `make types`) needs no env vars, while a missing setting still
    # stops startup.
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.log_level != "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logger.info("Starting Chatbot (log level: %s)", settings.log_level)
    start_mappers()
    yield
    await shutdown_engine()


async def health() -> dict:
    """Unauthenticated liveness probe (the deployment healthcheck hits this —
    every /conversations route requires a bearer token). Writes no access line."""
    return {"status": "ok"}


def create_app() -> FastAPI:
    app = FastAPI(title="Chatbot", version="0.1.0", lifespan=lifespan, responses=ERROR_RESPONSES)
    install_error_handlers(app)
    app.state.limiter = limiter
    # Kept out of the OpenAPI schema: the frontend never calls it (BLUEPRINT §6).
    app.add_api_route("/health", health, methods=["GET"], include_in_schema=False)
    app.add_middleware(RequestIdMiddleware)

    app.include_router(auth_router)
    app.include_router(conversations_router)
    return app


app = create_app()
