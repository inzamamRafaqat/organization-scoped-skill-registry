"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1.endpoints import skills, audit

api_router = APIRouter()

api_router.include_router(skills.router, prefix="/skills", tags=["Skills"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["Audit Logs"])
