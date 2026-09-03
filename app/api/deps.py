"""API dependencies for database session and actor authentication context."""
from typing import AsyncGenerator, Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.core.security import ActorContext


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides an asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_actor(
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> ActorContext:
    """
    Resolves the authenticated actor and organization boundary.

    Supports:
    1. Direct multi-tenant test headers:
       - X-Organization-Id: canonical organization identifier (e.g. org_abc, org_xyz)
       - X-User-Id: actor ID (e.g. alice_owner, bob_member)
       - X-User-Role: actor role ('owner', 'member', 'developer')
    2. Simulated Bearer token in format: 'Bearer <org_id>:<user_id>:<role>'

    Enforces that every request is strictly bound to an authenticated organization.
    """
    org_id = x_organization_id
    user_id = x_user_id
    role = (x_user_role or "member").lower()

    if not org_id and authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        parts = token.split(":")
        if len(parts) >= 2:
            org_id = parts[0]
            user_id = parts[1]
            if len(parts) >= 3:
                role = parts[2].lower()

    if not org_id or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Authentication required: Must provide 'X-Organization-Id' and 'X-User-Id' headers, "
                "or a Bearer token in format 'Bearer <org_id>:<user_id>:<role>'."
            ),
        )

    return ActorContext(
        actor_id=user_id,
        organization_id=org_id,
        role=role,
    )
