import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def add_audit_log(
    db: Session,
    *,
    company_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            metadata_json=metadata or {},
        )
    )
