"""Audit log API endpoints for retrieving tamper-evident tenant audit trails."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_actor
from app.core.security import ActorContext
from app.schemas.audit import AuditLogRead
from app.services.audit_service import AuditService

router = APIRouter()


@router.get(
    "",
    response_model=List[AuditLogRead],
    summary="List audit records for the current organization",
    description="Returns organization-scoped audit records containing organization, actor, event type, and version number.",
)
async def list_audit_logs(
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
):
    return await AuditService.list_organization_audit_logs(
        db,
        actor,
        limit=limit,
        offset=offset,
        resource_id=resource_id,
        event_type=event_type,
    )
