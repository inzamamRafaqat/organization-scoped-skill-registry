"""Skill service managing the lifecycle, versioning, authorization, and auditability of skills."""
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill
from app.models.skill_version import SkillVersion
from app.schemas.skill import (
    SkillDraftCreate,
    SkillVersionCreate,
    SkillActivateRequest,
    slugify,
)
from app.core.security import ActorContext
from app.services.audit_service import AuditService


class SkillService:
    @staticmethod
    async def create_draft(
        db: AsyncSession,
        actor: ActorContext,
        payload: SkillDraftCreate,
    ) -> Skill:
        """
        Creates a new skill in 'draft' status with an initial immutable version (v1).
        Audit logs the draft creation event.
        """
        skill_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        slug = payload.slug or slugify(payload.name)

        # 1. Create skill header in 'draft' status
        skill = Skill(
            id=skill_id,
            organization_id=actor.organization_id,
            name=payload.name,
            slug=slug,
            department=payload.department.lower().strip(),
            status="draft",
            current_version_id=None,  # Not active yet
            created_by=actor.actor_id,
        )
        db.add(skill)
        await db.flush()

        # 2. Create initial draft version (v1)
        initial_version = SkillVersion(
            id=version_id,
            skill_id=skill_id,
            organization_id=actor.organization_id,
            version_number=1,
            system_prompt=payload.system_prompt,
            description=payload.description,
            requested_tools=payload.requested_tools,
            created_by=actor.actor_id,
            is_immutable=True,
        )
        db.add(initial_version)
        await db.flush()

        # 3. Log audit record
        await AuditService.log_event(
            db=db,
            actor=actor,
            event_type="SKILL_DRAFT_CREATED",
            resource_type="skill",
            resource_id=skill_id,
            version_number=1,
            details={
                "name": payload.name,
                "department": skill.department,
                "initial_tools": payload.requested_tools,
            },
        )
        await db.commit()

        # Return refreshed skill with relations loaded
        return await SkillService.get_skill_by_id(db, actor, skill_id)

    @staticmethod
    async def get_skill_by_id(
        db: AsyncSession,
        actor: ActorContext,
        skill_id: str,
    ) -> Skill:
        """
        Retrieves a skill and its complete version history.
        Enforces strict tenant isolation:
        - If skill belongs to another tenant: returns 403 Forbidden and audit logs violation.
        - If skill does not exist: returns 404 Not Found.
        """
        # First query without tenant filter to detect cross-tenant intrusion
        query = (
            select(Skill)
            .options(
                selectinload(Skill.versions),
                selectinload(Skill.current_version),
            )
            .where(Skill.id == skill_id)
        )
        result = await db.execute(query)
        skill = result.scalars().first()

        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill '{skill_id}' not found.",
            )

        if skill.organization_id != actor.organization_id:
            # Cross-tenant access attempt detected! Log security audit record
            await AuditService.log_event(
                db=db,
                actor=actor,
                event_type="CROSS_TENANT_ACCESS_DENIED",
                resource_type="skill",
                resource_id=skill_id,
                details={
                    "target_organization_id": skill.organization_id,
                    "attempted_action": "read_skill",
                },
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-organization access denied: You cannot access skills belonging to another organization.",
            )

        return skill

    @staticmethod
    async def list_skills(
        db: AsyncSession,
        actor: ActorContext,
        department: Optional[str] = None,
        skill_status: Optional[str] = None,
    ) -> List[Skill]:
        """
        Lists all skills strictly scoped to the authenticated organization.
        """
        query = (
            select(Skill)
            .options(
                selectinload(Skill.versions),
                selectinload(Skill.current_version),
            )
            .where(Skill.organization_id == actor.organization_id)
            .order_by(Skill.created_at.desc())
        )
        if department:
            query = query.where(Skill.department == department.lower().strip())
        if skill_status:
            query = query.where(Skill.status == skill_status.lower().strip())

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def create_new_version(
        db: AsyncSession,
        actor: ActorContext,
        skill_id: str,
        payload: SkillVersionCreate,
    ) -> SkillVersion:
        """
        Creates a new immutable version for an existing skill.
        - Cross-organization updates are rejected.
        - Active skills cannot be mutated in place; changes must produce an incremented version.
        """
        skill = await SkillService.get_skill_by_id(db, actor, skill_id)

        # Compute next version number
        existing_version_numbers = [v.version_number for v in skill.versions]
        next_version = (max(existing_version_numbers) if existing_version_numbers else 0) + 1

        new_version_id = str(uuid.uuid4())
        version = SkillVersion(
            id=new_version_id,
            skill_id=skill.id,
            organization_id=actor.organization_id,
            version_number=next_version,
            system_prompt=payload.system_prompt,
            description=payload.description,
            requested_tools=payload.requested_tools,
            created_by=actor.actor_id,
            is_immutable=True,
        )
        db.add(version)
        await db.flush()

        # Audit log the version creation
        await AuditService.log_event(
            db=db,
            actor=actor,
            event_type="SKILL_VERSION_CREATED",
            resource_type="skill_version",
            resource_id=new_version_id,
            version_number=next_version,
            details={
                "skill_id": skill.id,
                "requested_tools": payload.requested_tools,
            },
        )
        await db.commit()
        return version

    @staticmethod
    async def activate_skill(
        db: AsyncSession,
        actor: ActorContext,
        skill_id: str,
        payload: Optional[SkillActivateRequest] = None,
    ) -> Skill:
        """
        Activates an approved skill version.
        Requirements:
        - Only organization owners can activate a skill.
        - Organization A cannot activate Organization B's skill.
        - Safe and idempotent: if already active at the target version, returns successfully without side effects.
        - Audit logs the activation event.
        """
        skill = await SkillService.get_skill_by_id(db, actor, skill_id)

        # Authorization: Only owners can activate
        if not actor.is_owner:
            await AuditService.log_event(
                db=db,
                actor=actor,
                event_type="UNAUTHORIZED_ACTIVATION_ATTEMPT",
                resource_type="skill",
                resource_id=skill.id,
                details={"reason": "Actor is not an organization owner", "role": actor.role},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: Only organization owners can activate a skill.",
            )

        # Determine target version
        target_version_number = payload.version_number if (payload and payload.version_number) else None

        if target_version_number is not None:
            target_version = next((v for v in skill.versions if v.version_number == target_version_number), None)
            if not target_version:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version {target_version_number} does not exist for skill '{skill_id}'.",
                )
        else:
            # Default to latest version
            if not skill.versions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot activate skill with no versions.",
                )
            target_version = max(skill.versions, key=lambda v: v.version_number)

        # Safe and idempotent check
        if skill.status == "active" and skill.current_version_id == target_version.id:
            # Idempotent response: already active with this version
            return skill

        # Perform activation
        previous_status = skill.status
        previous_version_id = skill.current_version_id
        skill.status = "active"
        skill.current_version_id = target_version.id
        skill.current_version = target_version
        db.add(skill)
        await db.flush()


        # Audit log activation
        await AuditService.log_event(
            db=db,
            actor=actor,
            event_type="SKILL_ACTIVATED",
            resource_type="skill",
            resource_id=skill.id,
            version_number=target_version.version_number,
            details={
                "previous_status": previous_status,
                "previous_version_id": previous_version_id,
                "activated_version_id": target_version.id,
                "tools": target_version.requested_tools,
            },
        )
        await db.commit()
        return await SkillService.get_skill_by_id(db, actor, skill_id)

    @staticmethod
    async def disable_skill(
        db: AsyncSession,
        actor: ActorContext,
        skill_id: str,
    ) -> Skill:
        """
        Disables a skill, immediately excluding it from runtime execution.
        """
        skill = await SkillService.get_skill_by_id(db, actor, skill_id)

        previous_status = skill.status
        skill.status = "disabled"
        db.add(skill)
        await db.flush()

        active_version_number = skill.current_version.version_number if skill.current_version else None
        await AuditService.log_event(
            db=db,
            actor=actor,
            event_type="SKILL_DISABLED",
            resource_type="skill",
            resource_id=skill.id,
            version_number=active_version_number,
            details={"previous_status": previous_status},
        )
        await db.commit()
        return await SkillService.get_skill_by_id(db, actor, skill_id)

    @staticmethod
    async def get_active_skills_for_department(
        db: AsyncSession,
        actor: ActorContext,
        department: str,
    ) -> List[Skill]:
        """
        Retrieves active skills for runtime selection by department.
        Draft and disabled skills are strictly excluded.
        Cross-organization skills are strictly excluded.
        """
        query = (
            select(Skill)
            .options(
                selectinload(Skill.versions),
                selectinload(Skill.current_version),
            )
            .where(
                and_(
                    Skill.organization_id == actor.organization_id,
                    Skill.department == department.lower().strip(),
                    Skill.status == "active",
                )
            )
            .order_by(Skill.name.asc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def execute_skill_runtime(
        db: AsyncSession,
        actor: ActorContext,
        skill_id: str,
        input_text: str,
    ) -> dict:
        """
        Executes a skill runtime call.
        Enforces that:
        - Draft skills cannot execute or load as active.
        - Disabled skills cannot execute.
        - Only active skills with valid current_version can execute.
        """
        skill = await SkillService.get_skill_by_id(db, actor, skill_id)

        if skill.status == "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Skill '{skill.name}' is in 'draft' status and cannot execute. It must be activated by an owner first.",
            )

        if skill.status == "disabled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Skill '{skill.name}' is disabled and excluded from runtime execution.",
            )

        if not skill.current_version:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Active skill does not have a current version assigned.",
            )

        version = skill.current_version
        return {
            "skill_id": skill.id,
            "version_number": version.version_number,
            "status": skill.status,
            "system_prompt": version.system_prompt,
            "active_tools": version.requested_tools,
            "simulated_result": f"[Simulated AI COO output for '{skill.name}' v{version.version_number}]: Processed input: '{input_text}'",
        }
