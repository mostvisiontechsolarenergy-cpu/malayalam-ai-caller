import base64
import hashlib
import hmac
from urllib.parse import urlencode, urlsplit, urlunsplit

from app.core.config import Settings, get_settings
from app.services.telephony.quick_tunnel import (
    get_configured_public_url,
    get_quick_tunnel_url,
)


def hash_webhook_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def webhook_token_matches(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_webhook_token(token), expected_hash)


def current_public_webhook_base_url(settings: Settings | None = None) -> str | None:
    selected = settings or get_settings()
    if selected.cloudflare_quick_tunnel_enabled:
        # Automatic tunnel mode must never fall back to a configured static URL.
        # A stale ngrok/previous-tunnel hostname can still look syntactically valid,
        # causing the carrier to accept a call and then disconnect as soon as it
        # cannot fetch the answer callback. Keep calling disabled until the current
        # supervised tunnel has passed its public health check.
        return get_quick_tunnel_url(verified_only=True)
    configured = (selected.public_webhook_base_url or "").strip().rstrip("/")
    if not configured.lower().startswith("https://"):
        return None
    if selected.app_env == "test":
        return configured
    verified = get_configured_public_url(verified_only=True)
    return verified if verified == configured else None


def public_callback_url(path: str, token: str, settings: Settings | None = None) -> str:
    base = current_public_webhook_base_url(settings)
    if not base:
        raise ValueError("The public HTTPS webhook is not ready")
    return f"{base}{path}?{urlencode({'token': token})}"


def public_static_url(path: str, settings: Settings | None = None) -> str:
    base = current_public_webhook_base_url(settings)
    if not base:
        raise ValueError("The public HTTPS webhook is not ready")
    return f"{base}{path}"


def public_websocket_url(path: str, token: str, settings: Settings | None = None) -> str:
    url = public_callback_url(path, token, settings)
    return "wss://" + url.removeprefix("https://")


def _base_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _expected_signature(message: str, auth_token: str) -> str:
    digest = hmac.new(auth_token.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def validate_vobiz_signature(
    url: str,
    headers: dict[str, str],
    settings: Settings | None = None,
) -> bool:
    selected = settings or get_settings()
    if not selected.vobiz_validate_signatures and selected.app_env != "production":
        return True
    if not selected.vobiz_auth_token:
        return False
    lowered = {key.lower(): value for key, value in headers.items()}
    base = _base_url(url)
    auth_token = selected.vobiz_auth_token.get_secret_value()
    v3_signature = lowered.get("x-vobiz-signature-v3", "")
    v3_nonce = lowered.get("x-vobiz-signature-v3-nonce", "")
    if v3_signature and v3_nonce:
        expected = _expected_signature(f"{base}.{v3_nonce}", auth_token)
        if hmac.compare_digest(v3_signature, expected):
            return True
    v2_signature = lowered.get("x-vobiz-signature-v2", "")
    v2_nonce = lowered.get("x-vobiz-signature-v2-nonce", "")
    if v2_signature and v2_nonce:
        expected = _expected_signature(f"{base}{v2_nonce}", auth_token)
        if hmac.compare_digest(v2_signature, expected):
            return True
    return False
