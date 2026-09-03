"""Pydantic schemas for skills and skill versions."""
import datetime
import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.core.tool_registry import validate_requested_tools, ToolValidationError


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


class SkillVersionBase(BaseModel):
    system_prompt: str = Field(..., min_length=5, description="System prompt defining the skill behavior")
    description: Optional[str] = Field(None, max_length=1000, description="Functional summary of the skill version")
    requested_tools: List[str] = Field(default_factory=list, description="List of tool capabilities required by the skill")

    @field_validator("requested_tools")
    @classmethod
    def check_tools(cls, v: List[str]) -> List[str]:
        try:
            validate_requested_tools(v)
        except ToolValidationError as e:
            raise ValueError(str(e))
        return v


class SkillVersionCreate(SkillVersionBase):
    pass


class SkillVersionRead(SkillVersionBase):
    id: str
    skill_id: str
    organization_id: str
    version_number: int
    created_by: str
    created_at: datetime.datetime
    is_immutable: bool

    model_config = ConfigDict(from_attributes=True)


class SkillDraftCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Human-readable name of the skill")
    slug: Optional[str] = Field(None, max_length=255, description="URL-friendly slug (auto-generated if omitted)")
    department: str = Field(..., min_length=2, max_length=100, description="Department owning or consuming this skill")
    system_prompt: str = Field(..., min_length=5, description="Initial system prompt")
    description: Optional[str] = Field(None, max_length=1000, description="Summary of the skill purpose")
    requested_tools: List[str] = Field(default_factory=list, description="Requested tool capabilities")

    @field_validator("requested_tools")
    @classmethod
    def check_tools(cls, v: List[str]) -> List[str]:
        try:
            validate_requested_tools(v)
        except ToolValidationError as e:
            raise ValueError(str(e))
        return v

    @field_validator("slug", mode="after")
    @classmethod
    def generate_slug_if_missing(cls, v: Optional[str], values) -> str:
        # Will be handled in service if None
        return v


class SkillActivateRequest(BaseModel):
    version_number: Optional[int] = Field(None, ge=1, description="Specific version number to activate (defaults to latest)")


class SkillRead(BaseModel):
    id: str
    organization_id: str
    name: str
    slug: str
    department: str
    status: str
    current_version_id: Optional[str] = None
    created_by: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    current_version: Optional[SkillVersionRead] = None
    versions: List[SkillVersionRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SkillSummary(BaseModel):
    id: str
    organization_id: str
    name: str
    slug: str
    department: str
    status: str
    current_version_id: Optional[str] = None
    created_by: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)



class SkillRuntimeExecutionRequest(BaseModel):
    input_text: str = Field(..., min_length=1, description="Input payload to test skill execution")


class SkillRuntimeExecutionResponse(BaseModel):
    skill_id: str
    version_number: int
    status: str
    system_prompt: str
    active_tools: List[str]
    simulated_result: str
