"""
Auth роутер.

POST /api/auth/register — регистрация с паролем
POST /api/auth/login    — вход с паролем

JWT payload: { sub: user_id, role: "employee", exp: ... }
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.api.schemas import LoginIn, LoginOut, RegisterIn, UserProfileOut
from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import Quest, QuestStatus, User, UserQuestProgress
from app.game.xp_engine import level_progress_pct, level_title, xp_to_next_level

log = logging.getLogger("firstshift.auth")
settings = get_settings()
router = APIRouter()

# bcrypt контекст — один на весь модуль
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def _initialize_quest_progress(db: Session, user: User) -> None:
    """Создать записи прогресса для всех квестов при первом входе."""
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
        progress = UserQuestProgress(
            user_id=user.id,
            quest_id=quest.id,
            status=(
                QuestStatus.AVAILABLE.value
                if quest.prerequisite_slug is None
                else QuestStatus.LOCKED.value
            ),
        )
        db.add(progress)
    db.flush()


def _build_profile(user: User) -> UserProfileOut:
    return UserProfileOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
        role=user.role,
        level=user.level,
        level_title=level_title(user.level),
        total_xp=user.total_xp,
        xp_to_next_level=xp_to_next_level(user.total_xp),
        level_progress_pct=level_progress_pct(user.total_xp),
        current_streak=user.current_streak,
    )


# ---------------------------------------------------------------------------
# Эндпоинты
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=LoginOut,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового сотрудника",
)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> LoginOut:
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким именем уже существует",
        )

    user = User(
        username=payload.username,
        display_name=payload.display_name or payload.username,
        password_hash=hash_password(payload.password),
        role="employee",
        level=1,
        total_xp=0,
    )
    db.add(user)
    db.flush()
    _initialize_quest_progress(db, user)
    db.commit()
    db.refresh(user)

    log.info("Новый пользователь: %s (id=%d, role=%s)", user.username, user.id, user.role)
    token = create_access_token(user.id, user.role)
    return LoginOut(access_token=token, token_type="bearer", user=_build_profile(user))


@router.post(
    "/login",
    response_model=LoginOut,
    summary="Вход по паролю",
)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> LoginOut:
    user = db.query(User).filter(User.username == payload.username).first()

    # Пользователь не найден — намеренно не говорим что именно не так
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    # Аккаунт без пароля (старый хакатонный аккаунт)
    if user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Этот аккаунт создан без пароля. Зарегистрируйся заново через /register.",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    # Инициализируем прогресс для новых квестов (если YAML обновился)
    _initialize_quest_progress(db, user)
    user.last_active_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    log.info("Вход: %s (id=%d, role=%s)", user.username, user.id, user.role)
    token = create_access_token(user.id, user.role)
    return LoginOut(access_token=token, token_type="bearer", user=_build_profile(user))
