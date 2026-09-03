"""Security primitives, authentication context, and tenant boundary enforcement."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ActorContext:
    """Represents the authenticated actor and their organization boundary context."""
    actor_id: str
    organization_id: str
    role: str
    name: Optional[str] = None

    @property
    def is_owner(self) -> bool:
        """Only organization owners can perform administrative actions like activating skills."""
        return self.role.lower() == "owner"

    def can_access_tenant(self, target_organization_id: str) -> bool:
        """Strict tenant isolation check: cross-tenant access is unconditionally denied."""
        return self.organization_id == target_organization_id
