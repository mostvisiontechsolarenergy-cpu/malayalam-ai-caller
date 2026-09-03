from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol


class NormalizedCallStatus(str, Enum):
    QUEUED = "QUEUED"
    INITIATED = "INITIATED"
    RINGING = "RINGING"
    ANSWERED = "ANSWERED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BUSY = "BUSY"
    NO_ANSWER = "NO_ANSWER"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class StartCallRequest:
    destination: str
    caller_id: str
    answer_url: str
    status_callback_url: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderCall:
    provider_call_id: str
    status: NormalizedCallStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)


class AudioConnection(Protocol):
    async def receive_bytes(self) -> bytes: ...
    async def send_bytes(self, data: bytes) -> None: ...


class TelephonyProvider(ABC):
    @abstractmethod
    async def start_call(self, request: StartCallRequest) -> ProviderCall: ...

    @abstractmethod
    async def end_call(self, provider_call_id: str) -> ProviderCall: ...

    @abstractmethod
    async def get_call_status(self, provider_call_id: str) -> NormalizedCallStatus: ...

    @abstractmethod
    async def handle_webhook(self, payload: bytes, headers: dict[str, str]) -> ProviderCall: ...

    @abstractmethod
    async def handle_audio_stream(self, connection: AudioConnection) -> None: ...

    @abstractmethod
    async def transfer_call(self, provider_call_id: str, destination: str) -> ProviderCall: ...

    @abstractmethod
    async def get_call_details(self, provider_call_id: str) -> ProviderCall: ...
