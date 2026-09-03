import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_id
from app.db.models import (
    FAQ,
    AIAgent,
    Client,
    KnowledgeItem,
    LeadStatus,
    Offer,
    Price,
    Product,
    Service,
)
from app.db.session import get_db
from app.schemas import DashboardSummary
from app.services.knowledge import current_record_predicates

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def count_records(db: Session, model: type, company_id: uuid.UUID, *predicates) -> int:
    value = db.scalar(
        select(func.count()).select_from(model).where(model.company_id == company_id, *predicates)
    )
    return int(value or 0)


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    lead_counts = {status.value: 0 for status in LeadStatus}
    rows = db.execute(
        select(Client.lead_status, func.count())
        .where(Client.company_id == company_id)
        .group_by(Client.lead_status)
    ).all()
    for lead_status, total in rows:
        key = lead_status.value if isinstance(lead_status, LeadStatus) else str(lead_status)
        lead_counts[key] = int(total)

    return DashboardSummary(
        clients_total=count_records(db, Client, company_id),
        lead_counts=lead_counts,
        products_total=count_records(db, Product, company_id),
        products_active=count_records(db, Product, company_id, Product.active.is_(True)),
        services_total=count_records(db, Service, company_id),
        services_active=count_records(db, Service, company_id, Service.active.is_(True)),
        current_prices=count_records(db, Price, company_id, *current_record_predicates(Price)),
        active_offers=count_records(db, Offer, company_id, *current_record_predicates(Offer)),
        active_faqs=count_records(db, FAQ, company_id, FAQ.active.is_(True)),
        active_knowledge_items=count_records(
            db, KnowledgeItem, company_id, *current_record_predicates(KnowledgeItem)
        ),
        active_ai_agents=count_records(db, AIAgent, company_id, AIAgent.active.is_(True)),
    )
