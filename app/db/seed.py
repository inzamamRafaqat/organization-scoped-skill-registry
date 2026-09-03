"""Database seeder for required fixture organizations and users."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User

FIXTURE_ORGS = [
    {"id": "org_abc", "name": "ABC Construction"},
    {"id": "org_xyz", "name": "XYZ Builders"},
]

FIXTURE_USERS = [
    # ABC Construction users
    {"id": "alice_owner", "organization_id": "org_abc", "email": "alice@abc-construction.local", "role": "owner", "name": "Alice Cooper (Owner)"},
    {"id": "bob_member", "organization_id": "org_abc", "email": "bob@abc-construction.local", "role": "member", "name": "Bob Martinez (Engineer)"},

    # XYZ Builders users
    {"id": "carol_owner", "organization_id": "org_xyz", "email": "carol@xyz-builders.local", "role": "owner", "name": "Carol Danvers (Owner)"},
    {"id": "dan_member", "organization_id": "org_xyz", "email": "dan@xyz-builders.local", "role": "member", "name": "Dan Vance (Project Manager)"},
]


async def seed_fixtures(db: AsyncSession) -> None:
    """Seeds the database with required fixture organizations and users if absent."""
    # Seed Organizations
    for org_data in FIXTURE_ORGS:
        result = await db.execute(select(Organization).where(Organization.id == org_data["id"]))
        if not result.scalars().first():
            org = Organization(**org_data)
            db.add(org)

    await db.flush()

    # Seed Users
    for user_data in FIXTURE_USERS:
        result = await db.execute(select(User).where(User.id == user_data["id"]))
        if not result.scalars().first():
            user = User(**user_data)
            db.add(user)

    await db.commit()
