"""
Pydantic v2 схемы — контракт API между backend и frontend.

Все Response-схемы заканчиваются на ...Out (то что отдаём клиенту).
Request-схемы заканчиваются на ...In (то что принимаем от клиента).
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginIn(BaseModel):
    username: str = Field(
        min_length=2,
        max_length=32,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        examples=["Parker"],
    )
    display_name: str | None = Field(
        default=None,
        max_length=64,
        description="Имя для отображения. Если не задано, используется username.",
    )


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Users / Profile
# ---------------------------------------------------------------------------

class UserProfileOut(BaseModel):
    id: int
    username: str
    display_name: str
    level: int
    level_title: str
    total_xp: int
    xp_to_next_level: int
    level_progress_pct: float = Field(ge=0.0, le=1.0)
    current_streak: int

    model_config = {"from_attributes": True}


class LoginOut(BaseModel):
    """Ответ на успешный логин: токен + профиль сразу."""
    access_token: str
    token_type: str = "bearer"
    user: UserProfileOut


# ---------------------------------------------------------------------------
# Quests
# ---------------------------------------------------------------------------

class QuestOut(BaseModel):
    slug: str
    title: str
    description: str
    type: str
    xp_reward: int
    difficulty: int
    story_chapter: int
    status: str
    params_json: str
    target_marker_id: int | None = None   # нужен фронту для CV-матчинга
    target_class: str | None = None        # нужен фронту для CV-матчинга

    model_config = {"from_attributes": True}


class QuestListOut(BaseModel):
    quests: list[QuestOut]
    total: int


class QuestStartOut(BaseModel):
    slug: str
    status: str
    message: str


class QuestCompleteOut(BaseModel):
    slug: str
    status: str
    xp_gained: int
    new_total_xp: int
    new_level: int
    leveled_up: bool
    newly_unlocked_achievements: list[dict] = []
    message: str


# ---------------------------------------------------------------------------
# Scan (будет расширяться на шаге 5)
# ---------------------------------------------------------------------------

class ScanEventIn(BaseModel):
    detected_class: str | None = None
    marker_id: int | None = None
    confidence: float | None = None
    quest_slug: str | None = None


class ScanEventOut(BaseModel):
    recorded: bool
    quest_slug: str | None = None
    message: str
