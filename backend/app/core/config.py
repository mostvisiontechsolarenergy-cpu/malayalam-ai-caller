from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Dcreation Maya API"
    app_env: str = "development"
    api_docs_enabled: bool = False
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    cors_origins: str = "http://localhost:3000"
    ai_provider: Literal["openai", "gemini"] = "openai"
    openai_api_key: SecretStr | None = None
    openai_text_model: str = "gpt-5.6-luna"
    openai_realtime_model: str = "gpt-realtime-2.1-mini"
    openai_realtime_transcription_model: str = "gpt-live-transcribe"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = Field(default=1024, ge=1024, le=1024)
    gemini_api_key: SecretStr | None = None
    gemini_text_model: str = "gemini-3.1-flash-lite"
    gemini_live_model: str = "gemini-3.1-flash-live-preview"
    gemini_voice: str = "Kore"
    upload_dir: str = "/app/uploads"
    document_max_size_mb: int = Field(default=15, ge=1, le=50)
    telephony_provider: Literal["vobiz"] = "vobiz"
    vobiz_auth_id: str | None = None
    vobiz_auth_token: SecretStr | None = None
    vobiz_phone_number: str | None = None
    vobiz_api_base_url: str = "https://api.vobiz.ai/api"
    vobiz_validate_signatures: bool = True
    cloudflare_quick_tunnel_enabled: bool = False
    public_webhook_base_url: str | None = None
    public_app_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    callback_scheduler_enabled: bool = True
    callback_scheduler_poll_seconds: float = Field(default=2.0, ge=0.5, le=60)
    callback_dispatch_grace_minutes: int = Field(default=15, ge=1, le=120)
    vobiz_inbound_forward_to: str | None = None
    automation_shared_secret: SecretStr | None = None

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def openai_key_configured(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.get_secret_value().strip())

    @property
    def gemini_key_configured(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.get_secret_value().strip())

    @property
    def ai_key_configured(self) -> bool:
        if self.ai_provider == "gemini":
            return self.gemini_key_configured
        return self.openai_key_configured

    @property
    def ai_text_model(self) -> str:
        return self.gemini_text_model if self.ai_provider == "gemini" else self.openai_text_model

    @property
    def ai_live_model(self) -> str:
        return (
            self.gemini_live_model if self.ai_provider == "gemini" else self.openai_realtime_model
        )

    @property
    def vobiz_configured(self) -> bool:
        return bool(
            self.vobiz_auth_id
            and self.vobiz_auth_id.strip()
            and self.vobiz_auth_token
            and self.vobiz_auth_token.get_secret_value().strip()
            and self.vobiz_phone_number
            and self.vobiz_phone_number.strip()
        )

    @property
    def public_webhook_configured(self) -> bool:
        return bool(
            self.cloudflare_quick_tunnel_enabled
            or self.public_webhook_base_url
            and self.public_webhook_base_url.strip().lower().startswith("https://")
        )

    @property
    def automation_configured(self) -> bool:
        return bool(
            self.automation_shared_secret
            and len(self.automation_shared_secret.get_secret_value().strip()) >= 32
        )

    @property
    def inbound_forward_configured(self) -> bool:
        return bool(self.vobiz_inbound_forward_to and self.vobiz_inbound_forward_to.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
