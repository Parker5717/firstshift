"""
ORM-модели FirstShift.

v3 (шаги 3-4): password_hash, role, mentor_id
"""

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(StrEnum):
    EMPLOYEE = "employee"
    MENTOR   = "mentor"
    HR       = "hr"
    ADMIN    = "admin"


class QuestType(StrEnum):
    DISCOVERY = "discovery"
    SAFETY    = "safety"
    KNOWLEDGE = "knowledge"
    SPEED_RUN = "speed_run"


class QuestStatus(StrEnum):
    LOCKED    = "locked"
    AVAILABLE = "available"
    ACTIVE    = "active"
    COMPLETED = "completed"
    FAILED    = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default=UserRole.EMPLOYEE.value)
    mentor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    level: Mapped[int] = mapped_column(Integer, default=1)
    total_xp: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    privacy_accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    quest_progress: Mapped[list["UserQuestProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    achievements: Mapped[list["UserAchievement"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    scan_events: Mapped[list["ScanEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    mentees: Mapped[list["User"]] = relationship(
        "User", foreign_keys="User.mentor_id", back_populates="mentor"
    )
    mentor: Mapped["User | None"] = relationship(
        "User", foreign_keys=[mentor_id], back_populates="mentees", remote_side="User.id"
    )

    def __repr__(self) -> str:
        return f"<User {self.username} role={self.role} lvl={self.level}>"


class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(32))
    target_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_marker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    xp_reward: Mapped[int] = mapped_column(Integer, default=50)
    prerequisite_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    story_chapter: Mapped[int] = mapped_column(Integer, default=1)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    params_json: Mapped[str] = mapped_column(Text, default="{}")

    progress_records: Mapped[list["UserQuestProgress"]] = relationship(
        back_populates="quest", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Quest {self.slug} ({self.type}, +{self.xp_reward} XP)>"


class UserQuestProgress(Base):
    __tablename__ = "user_quest_progress"
    __table_args__ = (UniqueConstraint("user_id", "quest_id", name="uq_user_quest"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=QuestStatus.LOCKED.value)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="quest_progress")
    quest: Mapped["Quest"] = relationship(back_populates="progress_records")


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(64), default="trophy")
    condition_json: Mapped[str] = mapped_column(Text)
    xp_bonus: Mapped[int] = mapped_column(Integer, default=0)


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), index=True
    )
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="achievements")
    achievement: Mapped["Achievement"] = relationship()


class ScanEvent(Base):
    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    detected_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    marker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    quest_id: Mapped[int | None] = mapped_column(
        ForeignKey("quests.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="scan_events")


# ── SafetyCheck ───────────────────────────────────────────────────────────────

class SafetyCheck(Base):
    """
    Результат ежедневной проверки СИЗ.
    Заменяет костыль с ScanEvent(detected_class='safety_check').

    client_id — UUID генерируется на фронте, используется для
    дедупликации офлайн-записей (шаг 8).
    """
    __tablename__ = "safety_checks"
    __table_args__ = (
        UniqueConstraint("user_id", "client_id", name="uq_safety_client"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    passed: Mapped[bool] = mapped_column(default=False)

    # Детали по каждому элементу СИЗ
    helmet: Mapped[bool] = mapped_column(default=False)
    vest: Mapped[bool] = mapped_column(default=False)
    goggles: Mapped[bool] = mapped_column(default=False)
    missing_items: Mapped[str] = mapped_column(String(256), default="")  # JSON-список

    # UUID для дедупликации офлайн-записей (шаг 8)
    client_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<SafetyCheck user={self.user_id} passed={self.passed} {self.timestamp}>"
