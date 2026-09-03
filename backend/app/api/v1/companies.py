import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.models import Company, User, UserRole
from app.db.session import get_db
from app.schemas import CompanyCreate, CompanyRead
from app.services.audit import add_audit_log

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyRead])
def list_companies(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Company]:
    statement = select(Company).order_by(Company.name)
    if current_user.role != UserRole.SUPER_ADMIN:
        statement = statement.where(Company.id == current_user.company_id)
    return list(db.scalars(statement).all())


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> Company:
    company = Company(name=payload.name)
    db.add(company)
    db.flush()
    add_audit_log(
        db,
        company_id=company.id,
        actor_user_id=current_user.id,
        action="CREATE",
        resource_type="COMPANY",
        resource_id=company.id,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Company name already exists") from exc
    db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    if current_user.role != UserRole.SUPER_ADMIN and current_user.company_id != company_id:
        raise HTTPException(status_code=404, detail="Company not found")
    company = db.scalar(select(Company).where(Company.id == company_id))
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
