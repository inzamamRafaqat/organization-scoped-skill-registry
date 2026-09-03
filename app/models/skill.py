"""Skill model representing organization-scoped AI COO skills."""
import datetime
import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Skill(Base):
    __tablename__ = "skills"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(64),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    department = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="draft", index=True)  # draft, active, disabled
    current_version_id = Column(
        String(36),
        ForeignKey("skill_versions.id", ondelete="SET NULL", use_alter=True, name="fk_skills_current_version_id"),
        nullable=True,
    )
    created_by = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    organization = relationship("Organization", back_populates="skills")
    versions = relationship(
        "SkillVersion",
        back_populates="skill",
        foreign_keys="[SkillVersion.skill_id]",
        cascade="all, delete-orphan",
        order_by="SkillVersion.version_number",
    )
    current_version = relationship(
        "SkillVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
