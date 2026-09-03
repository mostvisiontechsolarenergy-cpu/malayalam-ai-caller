from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_tenant_id
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import Company, User, UserRole
from app.db.session import get_db
from app.schemas import (
    BootstrapRequest,
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserRead,
)
from app.services.audit import add_audit_log

router = APIRouter(prefix="/auth", tags=["authentication"])


def token_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(
            subject=str(user.id),
            role=user.role.value,
            company_id=str(user.company_id) if user.company_id else None,
        )
    )


@router.post("/bootstrap", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def bootstrap(payload: BootstrapRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.scalar(select(func.count()).select_from(User)):
        raise HTTPException(status_code=409, detail="Bootstrap has already been completed")
    company = Company(name=payload.company_name)
    db.add(company)
    db.flush()
    user = User(
        company_id=company.id,
        name=payload.admin_name,
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        role=UserRole.SUPER_ADMIN,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bootstrap conflict") from exc
    db.refresh(user)
    return token_for(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_for(user)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_tenant_user(
    payload: UserCreate,
    company_id=Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if current_user.role == UserRole.STAFF:
        raise HTTPException(status_code=403, detail="Insufficient permission")
    if current_user.role == UserRole.ADMIN and payload.role != UserRole.STAFF:
        raise HTTPException(status_code=403, detail="Admins may create staff users only")
    user = User(
        company_id=company_id,
        name=payload.name,
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=current_user.id,
        action="CREATE",
        resource_type="USER",
        resource_id=user.id,
        metadata={"role": payload.role.value},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A user with this email already exists"
        ) from exc
    db.refresh(user)
    return user
