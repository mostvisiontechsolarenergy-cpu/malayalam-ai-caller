from fastapi import APIRouter

from app.api.v1 import (
    ai,
    auth,
    automation,
    companies,
    dashboard,
    knowledge,
    proposals,
    reports,
    resources,
    telephony,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(automation.router)
api_router.include_router(companies.router)
api_router.include_router(dashboard.router)
api_router.include_router(resources.router)
api_router.include_router(proposals.router)
api_router.include_router(reports.router)
api_router.include_router(knowledge.router)
api_router.include_router(ai.router)
api_router.include_router(telephony.router)
