"""Pydantic schemas for actor context and simulation."""
from typing import Optional
from pydantic import BaseModel


class ActorInfo(BaseModel):
    actor_id: str
    organization_id: str
    role: str
    name: Optional[str] = None
