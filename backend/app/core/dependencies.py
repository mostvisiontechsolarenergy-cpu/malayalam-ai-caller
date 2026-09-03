import uuid
from collections.abc import Callable

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import Company, User, UserRole
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access":
            raise credentials_error
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise credentials_error from exc
    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise credentials_error
    return user


def require_roles(*roles: UserRole) -> Callable[..., User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permission")
        return current_user

    return dependency


def get_tenant_id(
    x_company_id: uuid.UUID | None = Header(default=None, alias="X-Company-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    if current_user.role == UserRole.SUPER_ADMIN:
        company_id = x_company_id or current_user.company_id
    else:
        if x_company_id is not None and x_company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Cross-company access is forbidden")
        company_id = current_user.company_id
    if company_id is None:
        raise HTTPException(status_code=400, detail="X-Company-ID is required")
    company = db.scalar(
        select(Company).where(Company.id == company_id, Company.is_active.is_(True))
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company_id
