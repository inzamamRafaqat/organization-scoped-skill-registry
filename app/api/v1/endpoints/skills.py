"""Skill registry API endpoints for managing organization-scoped skills and versions."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_actor
from app.core.security import ActorContext
from app.schemas.skill import (
    SkillDraftCreate,
    SkillVersionCreate,
    SkillVersionRead,
    SkillRead,
    SkillSummary,
    SkillActivateRequest,
    SkillRuntimeExecutionRequest,
    SkillRuntimeExecutionResponse,
)
from app.services.skill_service import SkillService

router = APIRouter()


@router.post(
    "",
    response_model=SkillRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a skill draft",
    description="Creates a new skill in draft status with an initial immutable version (v1).",
)
async def create_skill_draft(
    payload: SkillDraftCreate,
    db: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
):
    return await SkillService.create_draft(db, actor, payload)


@router.get(
    "",
    response_model=List[SkillSummary],
    summary="List skills belonging to the current organization",
    description="Lists all skills owned by the caller's organization. Supports department and status filters.",
)
async def list_skills(
    department: Optional[str] = Query(None, description="Filter skills by department"),
    status: Optional[str] = Query(None, description="Filter skills by status (draft, active, disabled)"),
    db: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
):
    return await SkillService.list_skills(db, actor, department=department, skill_status=status)


@router.get(
    "/runtime/department/{department}",
    response_model=List[SkillRead],
    summary="Retrieve active skills for a department",
    description="Runtime selection query for AI COO agents. Only returns active skills belonging to the caller's organization.",
)
async def get_active_skills_for_department(
    department: str,
    db: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
):
    return await SkillService.get_active_skills_for_department(db, actor, department=department)


@router.get(
    "/{skill_id}",
    response_model=SkillRead,
    summary="Read one skill together with its versions",
    description="Fetches a skill, its current active version, and complete historical version list. Cross-tenant access is strictly denied.",
)
async def get_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
):
    return await SkillService.get_skill_by_id(db, actor, skill_id)


@router.post(
    "/{skill_id}/versions",
    response_model=SkillVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new immutable version",
    description="Creates an incremented immutable version for an existing skill. Changes to active skills must create a new version.",
)
async def create_skill_version(
    skill_id: str,
    payload: SkillVersionCreate,
    db: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
):
    return await SkillService.create_new_version(db, actor, skill_id, payload)


@router.post(
    "/{skill_id}/activate",
    response_model=SkillRead,
    summary="Activate an approved version",
    description="Activates an approved skill version. Requires organization owner role. Safe and idempotent.",
)
async def activate_skill(
    skill_id: str,
    payload: Optional[SkillActivateRequest] = None,
    db: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
):
    return await SkillService.activate_skill(db, actor, skill_id, payload)


@router.post(
    "/{skill_id}/disable",
    response_model=SkillRead,
    summary="Disable a skill",
    description="Transitions a skill to disabled status, immediately excluding it from department runtime selection.",
)
async def disable_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
):
    return await SkillService.disable_skill(db, actor, skill_id)


@router.post(
    "/{skill_id}/execute",
    response_model=SkillRuntimeExecutionResponse,
    summary="Simulate skill execution at runtime",
    description="Validates that only active skills with approved versions can execute; draft or disabled skills are rejected.",
)
async def execute_skill(
    skill_id: str,
    payload: SkillRuntimeExecutionRequest,
    db: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
):
    return await SkillService.execute_skill_runtime(db, actor, skill_id, payload.input_text)
