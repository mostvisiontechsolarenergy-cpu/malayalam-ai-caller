import re
import uuid
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_id, require_roles
from app.db.models import (
    Client,
    Company,
    Price,
    Product,
    Proposal,
    ProposalItem,
    ProposalItemSource,
    ProposalStatus,
    Service,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas import ProposalCreate, ProposalDetailRead, ProposalRead
from app.services.audit import add_audit_log
from app.services.proposals import build_proposal_pdf, proposal_display_title

router = APIRouter(prefix="/proposals", tags=["proposals"])
tenant_writer = require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
MONEY = Decimal("0.01")


def _catalog_description(
    requested_description: str | None, price: Price, catalog: object
) -> str | None:
    """Snapshot approved knowledge text so later catalog edits cannot alter a proposal."""
    if requested_description:
        return requested_description
    summary = (
        price.description
        or getattr(catalog, "full_description", None)
        or getattr(catalog, "short_description", None)
    )
    details = list(getattr(catalog, "features", None) or [])
    details.extend(getattr(catalog, "deliverables", None) or [])
    if not details:
        details.extend(getattr(catalog, "benefits", None) or [])
    parts = [str(summary).strip()] if summary else []
    parts.extend(str(detail).strip() for detail in details if str(detail).strip())
    return "\n".join(dict.fromkeys(parts)) or None


def _download_filename(client_name: str, title: str) -> str:
    safe_client = re.sub(r"[^A-Za-z0-9]+", "-", client_name).strip("-") or "Client"
    safe_title = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-") or "Business"
    return f"{safe_client}-{safe_title}-Proposal.pdf"


def _get_proposal(db: Session, company_id: uuid.UUID, proposal_id: uuid.UUID) -> Proposal:
    proposal = db.scalar(
        select(Proposal).where(
            Proposal.id == proposal_id,
            Proposal.company_id == company_id,
        )
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


def _get_items(db: Session, proposal_id: uuid.UUID) -> list[ProposalItem]:
    return list(
        db.scalars(
            select(ProposalItem)
            .where(ProposalItem.proposal_id == proposal_id)
            .order_by(ProposalItem.line_number)
        ).all()
    )


def _detail(proposal: Proposal, items: list[ProposalItem]) -> dict:
    data = ProposalRead.model_validate(proposal).model_dump()
    data["items"] = items
    return data


def _pdf_response(db: Session, proposal: Proposal) -> StreamingResponse:
    company = db.scalar(select(Company).where(Company.id == proposal.company_id))
    if company is None:
        raise HTTPException(status_code=409, detail="Proposal company is unavailable")
    client = SimpleNamespace(
        name=proposal.client_name,
        business_name=proposal.client_business_name,
        phone=proposal.client_phone,
        email=proposal.client_email,
        location=proposal.client_location,
    )
    items = _get_items(db, proposal.id)
    pdf = build_proposal_pdf(
        proposal=proposal,
        client=client,
        company=company,
        items=items,
    )
    filename = _download_filename(proposal.client_name, proposal_display_title(items))
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("", response_model=list[ProposalRead])
def list_proposals(
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[Proposal]:
    return list(
        db.scalars(
            select(Proposal)
            .where(Proposal.company_id == company_id)
            .order_by(Proposal.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


@router.post("", response_model=ProposalDetailRead, status_code=status.HTTP_201_CREATED)
def create_proposal(
    payload: ProposalCreate,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(tenant_writer),
    db: Session = Depends(get_db),
) -> dict:
    client = None
    if payload.client_id is not None:
        client = db.scalar(
            select(Client).where(Client.id == payload.client_id, Client.company_id == company_id)
        )
        if client is None:
            raise HTTPException(status_code=422, detail="Client does not belong to this company")

    client_name = payload.client_name or (client.name if client else None)
    if not client_name:
        raise HTTPException(status_code=422, detail="Client name is required")

    proposal = Proposal(
        company_id=company_id,
        client_id=client.id if client else None,
        client_name=client_name,
        client_business_name=payload.client_business_name
        or (client.business_name if client else None),
        client_phone=payload.client_phone or (client.phone if client else None),
        client_email=str(payload.client_email)
        if payload.client_email
        else (client.email if client else None),
        client_location=payload.client_location or (client.location if client else None),
        created_by_user_id=current_user.id,
        proposal_number=(
            f"PROP-{payload.proposal_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        ),
        proposal_date=payload.proposal_date,
        valid_until=payload.valid_until,
        project_start_date=payload.project_start_date,
        project_end_date=payload.project_end_date,
        status=ProposalStatus.DRAFT,
        currency=payload.currency,
        notes=payload.notes,
        terms=payload.terms,
        subtotal=Decimal("0"),
        total_amount=Decimal("0"),
    )
    db.add(proposal)
    db.flush()

    saved_items: list[ProposalItem] = []
    total = Decimal("0")
    for line_number, requested in enumerate(payload.items, start=1):
        if requested.price_id is not None:
            price = db.scalar(
                select(Price).where(
                    Price.id == requested.price_id,
                    Price.company_id == company_id,
                    Price.active.is_(True),
                )
            )
            if price is None:
                raise HTTPException(status_code=422, detail=f"Line {line_number}: price not found")
            if price.currency != payload.currency:
                raise HTTPException(
                    status_code=422,
                    detail=f"Line {line_number}: price currency must be {payload.currency}",
                )
            if price.valid_from and payload.proposal_date < price.valid_from:
                raise HTTPException(
                    status_code=422, detail=f"Line {line_number}: price is not active yet"
                )
            if price.valid_until and payload.proposal_date > price.valid_until:
                raise HTTPException(
                    status_code=422, detail=f"Line {line_number}: price has expired"
                )

            catalog = None
            if price.product_id:
                catalog = db.scalar(
                    select(Product).where(
                        Product.id == price.product_id,
                        Product.company_id == company_id,
                        Product.active.is_(True),
                    )
                )
            elif price.service_id:
                catalog = db.scalar(
                    select(Service).where(
                        Service.id == price.service_id,
                        Service.company_id == company_id,
                        Service.active.is_(True),
                    )
                )
            if catalog is None:
                raise HTTPException(
                    status_code=422, detail=f"Line {line_number}: catalog item is unavailable"
                )
            item_name = catalog.name
            package_name = price.package_name
            description = _catalog_description(requested.description, price, catalog)
            unit_price = Decimal(price.price)
            source_type = ProposalItemSource.CATALOG
            price_id = price.id
            product_id = price.product_id
            service_id = price.service_id
        else:
            item_name = requested.custom_name or "Custom service"
            package_name = "Custom service"
            description = requested.description or requested.custom_description
            unit_price = requested.custom_unit_price or Decimal("0")
            source_type = ProposalItemSource.CUSTOM
            price_id = None
            product_id = None
            service_id = None

        amount = (requested.quantity * unit_price).quantize(MONEY, rounding=ROUND_HALF_UP)
        saved = ProposalItem(
            company_id=company_id,
            proposal_id=proposal.id,
            price_id=price_id,
            product_id=product_id,
            service_id=service_id,
            source_type=source_type,
            line_number=line_number,
            item_name=item_name,
            package_name=package_name,
            description=description,
            quantity=requested.quantity,
            unit_price=unit_price,
            amount=amount,
            currency=payload.currency,
        )
        db.add(saved)
        saved_items.append(saved)
        total += amount

    proposal.subtotal = total.quantize(MONEY, rounding=ROUND_HALF_UP)
    proposal.total_amount = proposal.subtotal
    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=current_user.id,
        action="CREATE",
        resource_type="PROPOSAL",
        resource_id=proposal.id,
        metadata={"proposal_number": proposal.proposal_number, "line_count": len(saved_items)},
    )
    db.commit()
    db.refresh(proposal)
    for item in saved_items:
        db.refresh(item)
    return _detail(proposal, saved_items)


@router.get("/shared/{share_token}/pdf", include_in_schema=False)
def download_shared_proposal_pdf(
    share_token: str = Path(
        min_length=32,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    proposal = db.scalar(select(Proposal).where(Proposal.share_token == share_token))
    if proposal is None:
        raise HTTPException(status_code=404, detail="Shared proposal not found")
    return _pdf_response(db, proposal)


@router.get("/{proposal_id}", response_model=ProposalDetailRead)
def get_proposal(
    proposal_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> dict:
    proposal = _get_proposal(db, company_id, proposal_id)
    return _detail(proposal, _get_items(db, proposal.id))


@router.get("/{proposal_id}/pdf")
def download_proposal_pdf(
    proposal_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    proposal = _get_proposal(db, company_id, proposal_id)
    return _pdf_response(db, proposal)
