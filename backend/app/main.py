import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.services.telephony.call_batch_scheduler import supervise_call_batch_scheduler
from app.services.telephony.callback_scheduler import supervise_callback_scheduler
from app.services.telephony.quick_tunnel import (
    get_callback_status,
    supervise_configured_public_webhook,
    supervise_quick_tunnel,
)
from app.services.telephony.vobiz_security import current_public_webhook_base_url

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    tunnel_task: asyncio.Task[None] | None = None
    configured_webhook_task: asyncio.Task[None] | None = None
    callback_task: asyncio.Task[None] | None = None
    batch_task: asyncio.Task[None] | None = None
    if settings.cloudflare_quick_tunnel_enabled:
        tunnel_task = asyncio.create_task(supervise_quick_tunnel())
        logger.info("automatic_public_webhook_starting")
    elif settings.public_webhook_base_url:
        configured_webhook_task = asyncio.create_task(
            supervise_configured_public_webhook(settings.public_webhook_base_url)
        )
        logger.info("configured_public_webhook_monitor_starting")
    if settings.callback_scheduler_enabled and settings.app_env != "test":
        callback_task = asyncio.create_task(supervise_callback_scheduler())
        batch_task = asyncio.create_task(supervise_call_batch_scheduler())
    logger.info("application_started", environment=settings.app_env)
    try:
        yield
    finally:
        if tunnel_task is not None:
            tunnel_task.cancel()
            with suppress(asyncio.CancelledError):
                await tunnel_task
        if configured_webhook_task is not None:
            configured_webhook_task.cancel()
            with suppress(asyncio.CancelledError):
                await configured_webhook_task
        if callback_task is not None:
            callback_task.cancel()
            with suppress(asyncio.CancelledError):
                await callback_task
        if batch_task is not None:
            batch_task.cancel()
            with suppress(asyncio.CancelledError):
                await batch_task
        logger.info("application_stopped")


app = FastAPI(
    title=settings.app_name,
    version="0.5.0",
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Company-ID"],
)
app.include_router(api_router)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), payment=(), usb=()"
    return response


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    payload = {"status": "ok", "phase": "5"}
    if settings.app_env != "test":
        payload["calling_callback"] = (
            "ready" if current_public_webhook_base_url(settings) else "starting"
        )
        payload["calling_callback_detail"] = get_callback_status()
    return payload
