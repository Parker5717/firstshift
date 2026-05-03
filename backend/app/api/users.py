"""
Users роутер.

GET /api/users/me  — профиль текущего пользователя.
GET /api/users/leaderboard — топ-10 (заготовка, будет расширена на шаге 9).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import UserProfileOut
from app.db.database import get_db
from app.db.models import User
from app.game.xp_engine import level_progress_pct, level_title, xp_to_next_level

router = APIRouter()


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


@router.get(
    "/me",
    response_model=UserProfileOut,
    summary="Мой профиль",
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfileOut:
    """Возвращает профиль текущего авторизованного пользователя."""
    return _build_profile(current_user)


@router.get(
    "/leaderboard",
    response_model=list[UserProfileOut],
    summary="Топ-10 пользователей (заготовка)",
)
def leaderboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),  # только для авторизованных
) -> list[UserProfileOut]:
    """Топ-10 по XP. Будет доработан на шаге 9 (фильтрация по когорте)."""
    top = db.query(User).order_by(User.total_xp.desc()).limit(10).all()
    return [_build_profile(u) for u in top]
