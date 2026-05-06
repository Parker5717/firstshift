"""
Pydantic v2 схемы — контракт API между backend и frontend.

Изменения v2 (шаг 1):
- LoginIn     — добавлено поле password
- RegisterIn  — новая схема для регистрации
- UserProfileOut — добавлено поле role

Изменения (шаг 11):
- DisplayNameIn — схема для смены display_name
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterIn(BaseModel):
    username: str = Field(
        min_length=2,
        max_length=32,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        examples=["parker"],
    )
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = Field(default=None, max_length=64)
    privacy_accepted: bool = False


class LoginIn(BaseModel):
    username: str = Field(
        min_length=2,
        max_length=32,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )
    password: str = Field(min_length=1, max_length=128)


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
    role: str
    level: int
    level_title: str
    total_xp: int
    xp_to_next_level: int
    level_progress_pct: float = Field(ge=0.0, le=1.0)
    current_streak: int

    model_config = {"from_attributes": True}


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileOut


class DisplayNameIn(BaseModel):
    display_name: str = Field(
        min_length=1,
        max_length=64,
        strip_whitespace=True,
    )


class ProfileUpdateIn(BaseModel):
    display_name: str = Field(min_length=2, max_length=32)


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
    target_marker_id: int | None = None
    target_class: str | None = None

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
# Scan
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
