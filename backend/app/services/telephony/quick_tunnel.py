import asyncio
import contextlib
import re
from urllib.parse import urlsplit

import httpx
import structlog

logger = structlog.get_logger()

_TUNNEL_URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
_public_url: str | None = None
_public_verified = False
_configured_public_url: str | None = None
_configured_public_verified = False
_callback_status = "STARTING"


def get_callback_status() -> str:
    """Return a safe operational status without exposing provider or tunnel details."""
    return _callback_status


def set_callback_status(status: str) -> None:
    global _callback_status
    _callback_status = status


def get_quick_tunnel_url(*, verified_only: bool = False) -> str | None:
    if verified_only and not _public_verified:
        return None
    return _public_url


def set_quick_tunnel_url(url: str | None, *, verified: bool = False) -> None:
    global _public_url, _public_verified
    _public_url = url.rstrip("/") if url else None
    _public_verified = bool(_public_url and verified)
    if _public_verified:
        set_callback_status("READY")


def get_configured_public_url(*, verified_only: bool = False) -> str | None:
    if verified_only and not _configured_public_verified:
        return None
    return _configured_public_url


def set_configured_public_url(url: str | None, *, verified: bool = False) -> None:
    global _configured_public_url, _configured_public_verified
    _configured_public_url = url.rstrip("/") if url else None
    _configured_public_verified = bool(_configured_public_url and verified)
    set_callback_status("READY" if _configured_public_verified else "HEALTH_CHECK_PENDING")


def _mark_quick_tunnel_verified(url: str) -> None:
    global _public_verified
    if _public_url == url:
        _public_verified = True
        set_callback_status("READY")


async def wait_for_quick_tunnel(timeout_seconds: float = 75) -> str | None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        if _public_url:
            return _public_url
        await asyncio.sleep(0.2)
    return None


async def _wait_for_public_dns(url: str, timeout_seconds: float = 30) -> bool:
    hostname = urlsplit(url).hostname
    if not hostname:
        return False
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        try:
            await loop.getaddrinfo(hostname, 443)
            return True
        except OSError:
            await asyncio.sleep(1)
    return False


async def _verify_public_health(url: str) -> None:
    set_callback_status("HEALTH_CHECK_PENDING")
    async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
        while get_quick_tunnel_url() == url:
            try:
                response = await client.get(f"{url}/health")
                if response.status_code == 200 and response.json().get("status") == "ok":
                    _mark_quick_tunnel_verified(url)
                    logger.info("quick_tunnel_public_health_ready", public_url=url)
                    return
            except (httpx.HTTPError, ValueError):
                pass
            await asyncio.sleep(1)


async def public_health_is_ready(
    url: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bool:
    """Return whether a configured public callback currently reaches this backend."""
    candidate = url.strip().rstrip("/")
    if not candidate.lower().startswith("https://"):
        return False
    try:
        async with httpx.AsyncClient(
            timeout=5,
            trust_env=False,
            transport=transport,
        ) as client:
            response = await client.get(f"{candidate}/health")
        return bool(
            response.status_code == 200
            and response.headers.get("content-type", "").lower().startswith(
                "application/json"
            )
            and response.json().get("status") == "ok"
        )
    except (httpx.HTTPError, ValueError):
        return False


async def supervise_configured_public_webhook(url: str) -> None:
    candidate = url.strip().rstrip("/")
    set_configured_public_url(candidate, verified=False)
    last_ready: bool | None = None
    try:
        while True:
            ready = await public_health_is_ready(candidate)
            set_configured_public_url(candidate, verified=ready)
            if ready != last_ready:
                log = logger.info if ready else logger.warning
                log(
                    "configured_public_webhook_health_changed",
                    ready=ready,
                    public_url=candidate,
                )
                last_ready = ready
            await asyncio.sleep(5 if ready else 2)
    finally:
        set_configured_public_url(None)


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except TimeoutError:
        process.kill()
        await process.wait()


async def supervise_quick_tunnel(origin_url: str = "http://127.0.0.1:8000") -> None:
    retry_delay_seconds = 2.0
    while True:
        set_quick_tunnel_url(None)
        set_callback_status("STARTING")
        process: asyncio.subprocess.Process | None = None
        verification_task: asyncio.Task[None] | None = None
        rate_limited = False
        dns_failed = False
        try:
            process = await asyncio.create_subprocess_exec(
                "cloudflared",
                "tunnel",
                "--no-autoupdate",
                "--url",
                origin_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            if process.stdout is None:
                raise RuntimeError("cloudflared output stream is unavailable")
            async for raw_line in process.stdout:
                line = raw_line.decode(errors="replace")
                line_lower = line.lower()
                if "429 too many requests" in line_lower or "error code: 1015" in line_lower:
                    if not rate_limited:
                        logger.warning("quick_tunnel_rate_limited")
                    rate_limited = True
                    set_callback_status("PROVIDER_BUSY_RETRYING")
                match = _TUNNEL_URL_PATTERN.search(line)
                if match and match.group(0) != "https://api.trycloudflare.com":
                    current = match.group(0)
                    if current != get_quick_tunnel_url():
                        set_callback_status("DNS_PENDING")
                        logger.info("quick_tunnel_hostname_created", public_url=current)
                        if await _wait_for_public_dns(current):
                            set_quick_tunnel_url(current)
                            logger.info("quick_tunnel_dns_ready", public_url=current)
                            if verification_task is not None:
                                verification_task.cancel()
                            verification_task = asyncio.create_task(
                                _verify_public_health(current)
                            )
                        else:
                            dns_failed = True
                            set_callback_status("DNS_RETRYING")
                            logger.error("quick_tunnel_dns_unavailable", public_url=current)
                            # A quick-tunnel process can remain alive even when Cloudflare never
                            # publishes its generated hostname. Stop that unusable process so the
                            # supervisor requests a fresh hostname instead of remaining stuck.
                            await _stop_process(process)
                            break
                elif "failed to request quick Tunnel" in line:
                    logger.error("quick_tunnel_provider_error", detail=line.strip())
            return_code = await process.wait()
            logger.warning("quick_tunnel_stopped", return_code=return_code)
        except asyncio.CancelledError:
            if verification_task is not None:
                verification_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await verification_task
            if process is not None:
                await _stop_process(process)
            set_quick_tunnel_url(None)
            raise
        except Exception:
            set_callback_status("PROCESS_RETRYING")
            logger.exception("quick_tunnel_failed")
            if process is not None:
                with contextlib.suppress(Exception):
                    await _stop_process(process)
        if verification_task is not None:
            verification_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await verification_task
        set_quick_tunnel_url(None)
        if rate_limited:
            retry_delay_seconds = min(max(retry_delay_seconds * 2, 60), 600)
        elif dns_failed:
            retry_delay_seconds = min(max(retry_delay_seconds * 2, 15), 120)
        else:
            retry_delay_seconds = min(max(retry_delay_seconds * 2, 5), 60)
        logger.info("quick_tunnel_retry_scheduled", retry_seconds=retry_delay_seconds)
        if get_callback_status() == "STARTING":
            set_callback_status("PROCESS_RETRYING")
        await asyncio.sleep(retry_delay_seconds)
