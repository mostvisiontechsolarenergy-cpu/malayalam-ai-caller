from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs

import httpx
import structlog

from app.core.config import Settings, get_settings
from app.services.telephony.base import (
    AudioConnection,
    NormalizedCallStatus,
    ProviderCall,
    StartCallRequest,
    TelephonyProvider,
)

VOBIZ_STATUS_MAP = {
    "queued": NormalizedCallStatus.QUEUED,
    "initiated": NormalizedCallStatus.INITIATED,
    "ringing": NormalizedCallStatus.RINGING,
    "answered": NormalizedCallStatus.ANSWERED,
    "in-progress": NormalizedCallStatus.IN_PROGRESS,
    "active": NormalizedCallStatus.IN_PROGRESS,
    "completed": NormalizedCallStatus.COMPLETED,
    "busy": NormalizedCallStatus.BUSY,
    "no-answer": NormalizedCallStatus.NO_ANSWER,
    "failed": NormalizedCallStatus.FAILED,
    "cancel": NormalizedCallStatus.CANCELLED,
    "canceled": NormalizedCallStatus.CANCELLED,
    "cancelled": NormalizedCallStatus.CANCELLED,
    "timeout": NormalizedCallStatus.FAILED,
}
logger = structlog.get_logger()


class VobizProviderError(RuntimeError):
    pass


def normalize_vobiz_status(value: str | None) -> NormalizedCallStatus:
    return VOBIZ_STATUS_MAP.get((value or "").strip().lower(), NormalizedCallStatus.FAILED)


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class VobizProvider(TelephonyProvider):
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        if not self.settings.vobiz_configured:
            raise VobizProviderError(
                "The calling service is not configured. Complete the protected calling setup."
            )
        return {
            "X-Auth-ID": self.settings.vobiz_auth_id or "",
            "X-Auth-Token": self.settings.vobiz_auth_token.get_secret_value(),  # type: ignore[union-attr]
            "Content-Type": "application/json",
        }

    def _call_url(self, provider_call_id: str | None = None) -> str:
        base = self.settings.vobiz_api_base_url.rstrip("/")
        auth_id = self.settings.vobiz_auth_id or ""
        suffix = f"/{provider_call_id}" if provider_call_id else ""
        return f"{base}/v1/Account/{auth_id}/Call{suffix}/"

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text.strip()[:300]
        if isinstance(payload, dict):
            for key in ("error", "message", "detail"):
                if payload.get(key):
                    return str(payload[key])[:300]
        return str(payload)[:300]

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=20, transport=self.transport) as client:
                response = await client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json,
                    params=params,
                )
        except httpx.HTTPError as exc:
            logger.exception("calling_provider_connection_failed")
            raise VobizProviderError("Could not connect to the calling service") from exc
        if response.is_error:
            detail = self._error_detail(response)
            logger.error(
                "calling_provider_rejected_request",
                status_code=response.status_code,
                provider_detail=detail,
            )
            raise VobizProviderError(
                f"Calling service rejected the request ({response.status_code}). "
                f"Reference: CALL-{response.status_code}"
            )
        return response

    @staticmethod
    def _provider_call(payload: dict[str, Any], fallback_id: str = "") -> ProviderCall:
        calls = payload.get("calls")
        if isinstance(calls, list) and calls and isinstance(calls[0], dict):
            details = calls[0]
        else:
            details = payload
        provider_call_id = str(
            details.get("call_uuid")
            or details.get("request_uuid")
            or details.get("CallUUID")
            or fallback_id
        )
        status_value = (
            details.get("call_status")
            or details.get("call_state")
            or details.get("CallStatus")
            or details.get("Status")
            or (
                "queued"
                if str(details.get("message") or "").strip().lower()
                in {"call fired", "call queued"}
                else None
            )
        )
        return ProviderCall(
            provider_call_id=provider_call_id,
            status=normalize_vobiz_status(str(status_value) if status_value else None),
            duration_seconds=_as_int(
                details.get("call_duration")
                or details.get("duration")
                or details.get("Duration")
            ),
            provider_metadata=payload,
        )

    async def start_call(self, request: StartCallRequest) -> ProviderCall:
        response = await self._request(
            "POST",
            self._call_url(),
            json={
                "from": request.caller_id,
                "to": request.destination,
                "answer_url": request.answer_url,
                "answer_method": "POST",
                "hangup_url": request.status_callback_url,
                "hangup_method": "POST",
            },
        )
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("request_uuid"):
            raise VobizProviderError("The calling service accepted the request without a call ID")
        return self._provider_call(payload)

    async def end_call(self, provider_call_id: str) -> ProviderCall:
        await self._request("DELETE", self._call_url(provider_call_id))
        return ProviderCall(
            provider_call_id=provider_call_id,
            status=NormalizedCallStatus.COMPLETED,
            ended_at=datetime.now(UTC),
        )

    async def get_call_status(self, provider_call_id: str) -> NormalizedCallStatus:
        return (await self.get_call_details(provider_call_id)).status

    async def handle_webhook(self, payload: bytes, headers: dict[str, str]) -> ProviderCall:
        del headers
        values = {key: item[-1] for key, item in parse_qs(payload.decode()).items()}
        status = normalize_vobiz_status(values.get("CallStatus") or values.get("Status"))
        terminal = status in {
            NormalizedCallStatus.COMPLETED,
            NormalizedCallStatus.BUSY,
            NormalizedCallStatus.NO_ANSWER,
            NormalizedCallStatus.FAILED,
            NormalizedCallStatus.CANCELLED,
        }
        return ProviderCall(
            provider_call_id=values.get("CallUUID") or values.get("RequestUUID", ""),
            status=status,
            duration_seconds=_as_int(values.get("Duration") or values.get("BillDuration")),
            ended_at=datetime.now(UTC) if terminal else None,
            provider_metadata=values,
        )

    async def handle_audio_stream(self, connection: AudioConnection) -> None:
        del connection
        raise NotImplementedError("The secure audio bridge owns calling audio streams")

    async def transfer_call(self, provider_call_id: str, destination: str) -> ProviderCall:
        del provider_call_id, destination
        raise NotImplementedError("Call transfer is not enabled in the secure calling bridge")

    async def get_call_details(self, provider_call_id: str) -> ProviderCall:
        response = await self._request(
            "GET",
            self._call_url(provider_call_id),
            params={"status": "live"},
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise VobizProviderError("The calling service returned invalid call details")
        return self._provider_call(payload, provider_call_id)
