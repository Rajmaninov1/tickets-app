import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app.auth.router import router as auth_router
from app.core.config import configure_logging, get_settings
from app.core.router import router as core_router
from app.notifications.router import router as notifications_router
from app.realtime.broker import RabbitBroker
from app.realtime.hub import RealtimeHub
from app.realtime.router import router as ws_router
from app.tickets.router import router as tickets_router
from app.users.router import router as users_router
from app.web.router import router as web_router

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.debug(
        "Lifespan startup: ensuring data directories (data_dir=%s, upload_dir=%s)",
        settings.data_dir,
        settings.upload_dir,
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    hub = RealtimeHub()
    app.state.hub = hub
    app.state.broker = None
    logger.debug("RealtimeHub created.")

    # Try to connect to RabbitMQ with retries
    max_retries = 5
    retry_delay = 5
    for attempt in range(max_retries):
        try:
            logger.debug(
                "RabbitMQ connection attempt %d/%d url=%s",
                attempt + 1,
                max_retries,
                _redact_amqp(settings.rabbitmq_url),
            )
            broker = RabbitBroker(settings.rabbitmq_url, hub=hub)
            await broker.start()
            app.state.broker = broker
            logger.info("RabbitMQ broker connected successfully.")
            break
        except Exception:
            if attempt < max_retries - 1:
                logger.warning(
                    "RabbitMQ connection attempt %d/%d failed. Retrying in %ds...",
                    attempt + 1,
                    max_retries,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.warning(
                    "RabbitMQ broker failed to connect after %d attempts – realtime "
                    "events will be disabled.",
                    max_retries,
                    exc_info=True,
                )

    yield

    logger.debug("Lifespan shutdown: stopping broker if running.")
    if app.state.broker is not None:
        await app.state.broker.stop()
        logger.debug("RabbitMQ broker stopped.")


def _redact_amqp(url: str) -> str:
    """Avoid logging passwords from amqp URLs."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    creds, host = rest.rsplit("@", 1)
    if ":" in creds:
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{host}"
    return f"{scheme}://***@{host}"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.debug(
        "create_app: app_name=%s environment=%s log_level=%s",
        settings.app_name,
        settings.environment,
        settings.log_level,
    )

    app_kwargs = {"title": settings.app_name, "lifespan": lifespan}
    if settings.environment == "dev":
        app_kwargs["servers"] = [{"url": settings.base_url, "description": "Development server"}]

    app = FastAPI(**app_kwargs)

    # Rate limiter state
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Global exception handler – prevent leaking stack traces
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # Middleware (order matters: outermost first)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.debug(
            "Request started %s %s client=%s",
            request.method,
            request.url.path,
            request.client.host if request.client else None,
        )
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.debug(
            "Request finished %s %s -> %s (%.2f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    static_dir = Path("static")
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(web_router)
    app.include_router(core_router)
    app.include_router(auth_router)
    app.include_router(ws_router)
    app.include_router(tickets_router)
    app.include_router(notifications_router)
    app.include_router(users_router)

    return app


app = create_app()
