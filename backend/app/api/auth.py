"""
Auth роутер.

POST /api/auth/register — регистрация с паролем
POST /api/auth/login    — вход с паролем

JWT payload: { sub: user_id, role: "employee", exp: ... }
"""

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy.orm import Session

from app.api.schemas import LoginIn, LoginOut, RegisterIn, UserProfileOut
from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import Quest, QuestStatus, Tenant, User, UserQuestProgress
from app.game.xp_engine import level_progress_pct, level_title, xp_to_next_level

log = logging.getLogger("firstshift.auth")
settings = get_settings()
router = APIRouter()


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, role: str, tenant_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "tid": tenant_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def find_or_create_tenant(db: Session, company_code: str) -> tuple["Tenant", bool]:
    slug = company_code.lower().strip()
    tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if not tenant:
        tenant = Tenant(name=company_code, slug=slug)
        db.add(tenant)
        db.flush()
        return tenant, True
    return tenant, False


def _initialize_quest_progress(db: Session, user: User) -> None:
    all_quests = db.query(Quest).filter(
        (Quest.tenant_id == None) | (Quest.tenant_id == user.tenant_id)  # noqa: E711
    ).all()
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
        ui_mode=getattr(user, 'ui_mode', 'gamified') or 'gamified',
        tenant_id=user.tenant_id,
        tenant_slug=user.tenant.slug if user.tenant else "",
    )


# ---------------------------------------------------------------------------
# Эндпоинты
# ---------------------------------------------------------------------------

@router.post("/register", response_model=LoginOut, status_code=201, summary="Регистрация")
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> LoginOut:
    if not payload.privacy_accepted:
        raise HTTPException(status_code=400, detail="Необходимо принять политику обработки данных")

    tenant, is_new_tenant = find_or_create_tenant(db, payload.company_code)

    # В новом тенанте первый пользователь получает роль admin
    existing_count = db.query(User).filter(User.tenant_id == tenant.id).count()
    role = "admin" if existing_count == 0 else "employee"

    if db.query(User).filter(User.tenant_id == tenant.id, User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="Пользователь с таким именем уже существует")

    ui_mode = "gamified"
    if payload.birth_year:
        age = datetime.now().year - payload.birth_year
        ui_mode = "gamified" if age < 30 else "regulation"

    user = User(
        tenant_id=tenant.id,
        username=payload.username,
        display_name=payload.display_name or payload.username,
        password_hash=hash_password(payload.password),
        role=role,
        level=1,
        total_xp=0,
        privacy_accepted_at=datetime.now(timezone.utc),
        birth_year=payload.birth_year,
        ui_mode=ui_mode,
    )
    db.add(user)
    db.flush()
    _initialize_quest_progress(db, user)
    db.commit()
    db.refresh(user)

    log.info("Новый пользователь: %s (id=%d, tenant=%s, role=%s)", user.username, user.id, tenant.slug, user.role)
    return LoginOut(
        access_token=create_access_token(user.id, user.role, user.tenant_id),
        token_type="bearer",
        user=_build_profile(user),
    )


@router.post("/login", response_model=LoginOut, summary="Вход по паролю")
def login(payload: LoginIn, db: Session = Depends(get_db)) -> LoginOut:
    # Ищем пользователя глобально по username (логин уникален только в рамках тенанта,
    # но для входа нам нужен company_code чтобы различить тенанты.
    # Пока ищем первый совпадающий — в будущем добавить company_code в форму входа.)
    user = db.query(User).filter(User.username == payload.username).first()

    if user is None or user.password_hash is None:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    _initialize_quest_progress(db, user)
    user.last_active_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    log.info("Вход: %s (id=%d, role=%s, tenant=%d)", user.username, user.id, user.role, user.tenant_id)
    return LoginOut(
        access_token=create_access_token(user.id, user.role, user.tenant_id),
        token_type="bearer",
        user=_build_profile(user),
    )
