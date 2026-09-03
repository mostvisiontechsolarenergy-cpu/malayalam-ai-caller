import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.crud import create_crud_router
from app.core.dependencies import get_tenant_id
from app.db.models import FAQ, AIAgent, Client, KnowledgeItem, Offer, Price, Product, Service
from app.db.session import get_db
from app.schemas import (
    AIAgentCreate,
    AIAgentRead,
    AIAgentUpdate,
    ClientCreate,
    ClientRead,
    ClientUpdate,
    FAQCreate,
    FAQRead,
    FAQUpdate,
    KnowledgeCreate,
    KnowledgeRead,
    KnowledgeSearchResult,
    KnowledgeUpdate,
    OfferCreate,
    OfferRead,
    OfferUpdate,
    PriceCreate,
    PriceRead,
    PriceUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
)
from app.services.knowledge import KnowledgeService, current_record_predicates


def validate_catalog_target(
    db: Session,
    company_id: uuid.UUID,
    data: dict[str, Any],
    existing: Price | Offer | None,
) -> None:
    product_id = data.get("product_id", existing.product_id if existing else None)
    service_id = data.get("service_id", existing.service_id if existing else None)
    if isinstance(existing, Price) or existing is None and "billing_type" in data:
        if (product_id is None) == (service_id is None):
            raise HTTPException(
                status_code=422,
                detail="Price must target exactly one product or service",
            )
    elif product_id and service_id:
        raise HTTPException(status_code=422, detail="Offer cannot target both product and service")
    if (
        product_id
        and db.scalar(
            select(Product.id).where(Product.id == product_id, Product.company_id == company_id)
        )
        is None
    ):
        raise HTTPException(status_code=422, detail="Product does not belong to this company")
    if (
        service_id
        and db.scalar(
            select(Service.id).where(Service.id == service_id, Service.company_id == company_id)
        )
        is None
    ):
        raise HTTPException(status_code=422, detail="Service does not belong to this company")


def current_filter(model: type) -> list:
    return current_record_predicates(model)


router = APIRouter()


@router.get(
    "/knowledge/search",
    response_model=list[KnowledgeSearchResult],
    tags=["knowledge"],
)
def search_knowledge(
    q: str = Query(min_length=1, max_length=300),
    limit: int = Query(default=10, ge=1, le=25),
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> list[KnowledgeSearchResult]:
    return KnowledgeService(db, company_id).search_knowledge(q, limit)


router.include_router(
    create_crud_router(
        prefix="/clients",
        tag="clients",
        model=Client,
        create_schema=ClientCreate,
        update_schema=ClientUpdate,
        read_schema=ClientRead,
    )
)
router.include_router(
    create_crud_router(
        prefix="/products",
        tag="products",
        model=Product,
        create_schema=ProductCreate,
        update_schema=ProductUpdate,
        read_schema=ProductRead,
    )
)
router.include_router(
    create_crud_router(
        prefix="/services",
        tag="services",
        model=Service,
        create_schema=ServiceCreate,
        update_schema=ServiceUpdate,
        read_schema=ServiceRead,
    )
)
router.include_router(
    create_crud_router(
        prefix="/prices",
        tag="prices",
        model=Price,
        create_schema=PriceCreate,
        update_schema=PriceUpdate,
        read_schema=PriceRead,
        validator=validate_catalog_target,
        current_filter=current_filter,
    )
)
router.include_router(
    create_crud_router(
        prefix="/offers",
        tag="offers",
        model=Offer,
        create_schema=OfferCreate,
        update_schema=OfferUpdate,
        read_schema=OfferRead,
        validator=validate_catalog_target,
        current_filter=current_filter,
    )
)
router.include_router(
    create_crud_router(
        prefix="/faqs",
        tag="faqs",
        model=FAQ,
        create_schema=FAQCreate,
        update_schema=FAQUpdate,
        read_schema=FAQRead,
        current_filter=current_filter,
    )
)
router.include_router(
    create_crud_router(
        prefix="/knowledge-items",
        tag="knowledge",
        model=KnowledgeItem,
        create_schema=KnowledgeCreate,
        update_schema=KnowledgeUpdate,
        read_schema=KnowledgeRead,
        current_filter=current_filter,
    )
)
router.include_router(
    create_crud_router(
        prefix="/ai-agents",
        tag="ai-agents",
        model=AIAgent,
        create_schema=AIAgentCreate,
        update_schema=AIAgentUpdate,
        read_schema=AIAgentRead,
    )
)
