"""Pydantic schemas for audit logging."""
import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class AuditLogRead(BaseModel):
    id: str
    organization_id: str
    actor_id: str
    actor_role: str
    event_type: str
    resource_type: str
    resource_id: str
    version_number: Optional[int] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

