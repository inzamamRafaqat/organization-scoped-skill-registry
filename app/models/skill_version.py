"""SkillVersion model representing immutable versions of a skill."""
import datetime
import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class SkillVersion(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "version_number", name="uq_skill_version_number"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    skill_id = Column(
        String(36),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Redundant tenant key stored for direct indexed tenant isolation
    organization_id = Column(
        String(64),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False, index=True)
    system_prompt = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    requested_tools = Column(JSON, nullable=False, default=list)
    created_by = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    is_immutable = Column(Boolean, nullable=False, default=True)

    skill = relationship("Skill", back_populates="versions", foreign_keys=[skill_id])
