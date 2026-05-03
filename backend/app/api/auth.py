"""
Auth роутер — POST /api/auth/login.

Логика намеренно упрощена для хакатона:
- Пароль не нужен. Ввёл никнейм — вошёл (или зарегистрировался).
- Если юзера нет — создаётся автоматически.
- Возвращается JWT-токен + профиль пользователя.

Все остальные эндпоинты принимают этот токен в заголовке:
  Authorization: Bearer <token>
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy.orm import Session

from app.api.schemas import LoginIn, LoginOut, UserProfileOut
from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import Quest, QuestStatus, User, UserQuestProgress
from app.game.xp_engine import level_from_xp, level_progress_pct, level_title, xp_to_next_level

log = logging.getLogger("casper.auth")
settings = get_settings()
router = APIRouter()


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def _initialize_quest_progress(db: Session, user: User) -> None:
    """
    При первом входе создаёт записи UserQuestProgress для всех квестов.
    Квесты без prerequisite → AVAILABLE, остальные → LOCKED.
    Уже существующие записи не трогаем.
    """
    all_quests = db.query(Quest).all()
    existing_slugs = {
        p.quest.slug for p in db.query(UserQuestProgress)
        .filter(UserQuestProgress.user_id == user.id)
        .join(UserQuestProgress.quest)
        .all()
    }

    for quest in all_quests:
        if quest.slug in existing_slugs:
            continue
        status_val = (
            QuestStatus.AVAILABLE.value
            if quest.prerequisite_slug is None
            else QuestStatus.LOCKED.value
        )
        progress = UserQuestProgress(
            user_id=user.id,
            quest_id=quest.id,
            status=status_val,
        )
        db.add(progress)

    db.flush()


def _build_profile(user: User) -> UserProfileOut:
    return UserProfileOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
        level=user.level,
        level_title=level_title(user.level),
        total_xp=user.total_xp,
        xp_to_next_level=xp_to_next_level(user.total_xp),
        level_progress_pct=level_progress_pct(user.total_xp),
        current_streak=user.current_streak,
    )


@router.post(
    "/login",
    response_model=LoginOut,
    summary="Войти или зарегистрироваться",
    description=(
        "Если пользователь с таким username уже есть — выполняется вход. "
        "Если нет — создаётся новый аккаунт. Пароль не нужен."
    ),
)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> LoginOut:
    user = db.query(User).filter(User.username == payload.username).first()

    if user is None:
        # Новый пользователь
        user = User(
            username=payload.username,
            display_name=payload.display_name or payload.username,
            level=1,
            total_xp=0,
        )
        db.add(user)
        db.flush()  # получаем user.id до инициализации прогресса
        _initialize_quest_progress(db, user)
        db.commit()
        db.refresh(user)
        log.info("Новый пользователь зарегистрирован: %s (id=%d)", user.username, user.id)
    else:
        # Обновляем display_name если передан
        if payload.display_name:
            user.display_name = payload.display_name
        # Инициализируем прогресс для новых квестов (если YAML обновился)
        _initialize_quest_progress(db, user)
        user.last_active_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
        log.info("Вход: %s (id=%d, level=%d, xp=%d)", user.username, user.id, user.level, user.total_xp)

    token = create_access_token(user.id)
    return LoginOut(
        access_token=token,
        token_type="bearer",
        user=_build_profile(user),
    )
