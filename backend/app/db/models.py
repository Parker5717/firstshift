"""
ORM-модели CASPER AR Assistant.

Архитектурные решения:
- Quest и Achievement — статика, грузится из YAML при старте (см. game/content/).
  В БД они нужны только для FK с UserQuestProgress / UserAchievement и для
  истории скан-событий. При изменении YAML — пересеять БД.
- Прогресс пользователя хранится отдельно от квестов (классический many-to-many
  через ассоциативную таблицу с дополнительными полями).
- ScanEvent — лог всех успешных детекций. Нужен для:
    1) анти-чита (нельзя получить XP за один и тот же объект 100 раз подряд),
    2) аналитики ("какие квесты проходят чаще всего"),
    3) ачивок типа "отсканируй 10 разных объектов".
"""

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    """UTC-время с timezone-aware datetime. SQLite его игнорит, но для PG важно."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class QuestType(StrEnum):
    DISCOVERY = "discovery"      # "найди и отсканируй объект X"
    SAFETY = "safety"            # "пройди проверку СИЗ"
    KNOWLEDGE = "knowledge"      # "ответь на квиз после сканирования"
    SPEED_RUN = "speed_run"      # "найди N объектов за T минут"


class QuestStatus(StrEnum):
    LOCKED = "locked"            # ещё не открыт (есть невыполненный prerequisite)
    AVAILABLE = "available"      # можно начинать
    ACTIVE = "active"            # пользователь начал, но не завершил
    COMPLETED = "completed"      # успешно завершён
    FAILED = "failed"            # speed_run провален (не уложился по времени)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")

    # Прогресс
    level: Mapped[int] = mapped_column(Integer, default=1)
    total_xp: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)  # дней подряд

    # Тайминг
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Связи
    quest_progress: Mapped[list["UserQuestProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    achievements: Mapped[list["UserAchievement"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    scan_events: Mapped[list["ScanEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.username} lvl={self.level} xp={self.total_xp}>"


# ---------------------------------------------------------------------------
# Quests (контент)
# ---------------------------------------------------------------------------

class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)

    # Тип квеста определяет, как его валидировать (см. quest_manager.py)
    type: Mapped[str] = mapped_column(String(32))  # значения из QuestType

    # Что именно искать. Один из двух способов идентификации:
    #   target_class    — имя класса для нейросети (например "fire_extinguisher")
    #   target_marker_id — ID ArUco-маркера (например 7)
    # Если оба None — квест валидируется кастомной логикой (например speed_run).
    target_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_marker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Награда и порядок прохождения
    xp_reward: Mapped[int] = mapped_column(Integer, default=50)
    prerequisite_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    story_chapter: Mapped[int] = mapped_column(Integer, default=1)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)  # 1-5

    # Доп. параметры в JSON-подобной строке (для speed_run: {"count": 5, "time_sec": 180})
    params_json: Mapped[str] = mapped_column(Text, default="{}")

    # Связи
    progress_records: Mapped[list["UserQuestProgress"]] = relationship(
        back_populates="quest", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Quest {self.slug} ({self.type}, +{self.xp_reward} XP)>"


# ---------------------------------------------------------------------------
# Прогресс пользователя по квестам
# ---------------------------------------------------------------------------

class UserQuestProgress(Base):
    __tablename__ = "user_quest_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "quest_id", name="uq_user_quest"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id", ondelete="CASCADE"), index=True)

    status: Mapped[str] = mapped_column(String(16), default=QuestStatus.LOCKED.value)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Связи
    user: Mapped["User"] = relationship(back_populates="quest_progress")
    quest: Mapped["Quest"] = relationship(back_populates="progress_records")


# ---------------------------------------------------------------------------
# Achievements (контент)
# ---------------------------------------------------------------------------

class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(64), default="trophy")  # имя иконки во фронте

    # JSON-условие срабатывания, проверяется в game/achievements.py
    # Примеры:
    #   {"type": "scan_count", "min": 10}
    #   {"type": "level_reached", "min": 5}
    #   {"type": "quest_completed", "slug": "boss_inspection"}
    condition_json: Mapped[str] = mapped_column(Text)

    xp_bonus: Mapped[int] = mapped_column(Integer, default=0)  # доп. XP при разблокировке


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), index=True
    )
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="achievements")
    achievement: Mapped["Achievement"] = relationship()


# ---------------------------------------------------------------------------
# Лог сканирований
# ---------------------------------------------------------------------------

class ScanEvent(Base):
    """
    Каждое успешное распознавание объекта или маркера — одна запись.
    Используется для анти-чита, аналитики и условий ачивок.
    """
    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    detected_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    marker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Если скан был засчитан в рамках квеста — фиксируем какого
    quest_id: Mapped[int | None] = mapped_column(
        ForeignKey("quests.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="scan_events")
