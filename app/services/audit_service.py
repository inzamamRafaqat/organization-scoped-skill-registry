"""Audit service for logging all tenant security and lifecycle events."""
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.core.security import ActorContext


class AuditService:
    @staticmethod
    async def log_event(
        db: AsyncSession,
        actor: ActorContext,
        event_type: str,
        resource_type: str,
        resource_id: str,
        version_number: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        organization_id_override: Optional[str] = None,
    ) -> AuditLog:
        """
        Records an append-only audit trail entry.

        Strictly records:
        - organization_id
        - actor_id and actor_role
        - event_type
        - resource_type and resource_id
        - version_number (if applicable)
        - details / metadata
        """
        org_id = organization_id_override or actor.organization_id
        entry = AuditLog(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=str(resource_id),
            version_number=version_number,
            details=details or {},
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def list_organization_audit_logs(
        db: AsyncSession,
        actor: ActorContext,
        limit: int = 50,
        offset: int = 0,
        resource_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[AuditLog]:
        """Lists audit logs scoped exclusively to the authenticated actor's organization."""
        query = (
            select(AuditLog)
            .where(AuditLog.organization_id == actor.organization_id)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
            .offset(offset)
        )
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        if event_type:
            query = query.where(AuditLog.event_type == event_type)

        result = await db.execute(query)
        return list(result.scalars().all())
