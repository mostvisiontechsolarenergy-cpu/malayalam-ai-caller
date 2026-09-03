from datetime import UTC, datetime
from hmac import compare_digest

from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import get_settings

router = APIRouter(prefix="/automation", tags=["automation"])


def require_automation_secret(
    x_automation_secret: str | None = Header(default=None, alias="X-Automation-Secret"),
) -> None:
    settings = get_settings()
    if not settings.automation_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Automation connector is not configured",
        )
    expected = settings.automation_shared_secret
    if expected is None or x_automation_secret is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid automation credential",
        )
    if not compare_digest(x_automation_secret, expected.get_secret_value()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid automation credential",
        )


@router.get("/status")
def automation_status(
    x_automation_secret: str | None = Header(default=None, alias="X-Automation-Secret"),
) -> dict[str, str]:
    require_automation_secret(x_automation_secret)
    settings = get_settings()
    return {
        "status": "ready",
        "application": settings.app_name,
        "environment": settings.app_env,
        "connector": "automation",
        "timestamp": datetime.now(UTC).isoformat(),
    }
