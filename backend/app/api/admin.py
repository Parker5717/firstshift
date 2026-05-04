"""
Admin роутер — эндпоинты для HR и администраторов.

Доступ:
  GET  /api/admin/users                — список сотрудников (hr, admin)
  GET  /api/admin/users/{id}           — детали сотрудника (hr, admin)
  PATCH /api/admin/users/{id}/role     — сменить роль (только admin)
  GET  /api/admin/safety/today         — кто прошёл Safety Check сегодня (hr, admin)
"""

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.api.schemas import UserProfileOut
from app.db.database import get_db
from app.db.models import Quest, QuestStatus, User, UserQuestProgress
from app.game.xp_engine import level_progress_pct, level_title, xp_to_next_level

log = logging.getLogger("firstshift.admin")
router = APIRouter()

VALID_ROLES = {"employee", "mentor", "hr", "admin"}


# ---------------------------------------------------------------------------
# Схемы
# ---------------------------------------------------------------------------

class EmployeeOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    level: int
    level_title: str
    total_xp: int
    quests_completed: int
    quests_total: int
    completion_pct: float
    created_at: datetime
    last_active_at: datetime

    model_config = {"from_attributes": True}


class RolePatchIn(BaseModel):
    role: str


class SafetyStatusOut(BaseModel):
    user_id: int
    username: str
    display_name: str
    passed_today: bool
    last_check_at: datetime | None = None


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

def _employee_out(user: User, db: Session) -> EmployeeOut:
    total = db.query(UserQuestProgress).filter(
        UserQuestProgress.user_id == user.id
    ).count()
    completed = db.query(UserQuestProgress).filter(
        UserQuestProgress.user_id == user.id,
        UserQuestProgress.status == QuestStatus.COMPLETED.value,
    ).count()

    return EmployeeOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
        role=user.role,
        level=user.level,
        level_title=level_title(user.level),
        total_xp=user.total_xp,
        quests_completed=completed,
        quests_total=total,
        completion_pct=round(completed / total * 100, 1) if total else 0.0,
        created_at=user.created_at,
        last_active_at=user.last_active_at,
    )


# ---------------------------------------------------------------------------
# Эндпоинты
# ---------------------------------------------------------------------------

@router.get(
    "/users",
    response_model=list[EmployeeOut],
    summary="Список всех сотрудников",
)
def list_employees(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("hr", "admin")),
) -> list[EmployeeOut]:
    users = db.query(User).order_by(User.total_xp.desc()).all()
    return [_employee_out(u, db) for u in users]


@router.get(
    "/users/{user_id}",
    response_model=EmployeeOut,
    summary="Детали сотрудника",
)
def get_employee(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("hr", "admin")),
) -> EmployeeOut:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return _employee_out(user, db)


@router.patch(
    "/users/{user_id}/role",
    response_model=dict,
    summary="Сменить роль сотрудника (только admin)",
)
def set_role(
    user_id: int,
    body: RolePatchIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
) -> dict:
    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимая роль. Варианты: {', '.join(VALID_ROLES)}",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя менять собственную роль")

    old_role  = user.role
    user.role = body.role
    db.commit()

    log.info("Admin %s: роль %s → %s для %s", admin.username, old_role, body.role, user.username)
    return {"ok": True, "user_id": user_id, "role": body.role}


@router.get(
    "/safety/today",
    response_model=list[SafetyStatusOut],
    summary="Safety Check сегодня — кто прошёл",
)
def safety_today(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("hr", "admin")),
) -> list[SafetyStatusOut]:
    """
    Пока safety_checks таблицы нет (шаг 5) — определяем по ScanEvent
    с detected_class='safety_check'. После шага 5 заменим на настоящую таблицу.
    """
    from app.db.models import ScanEvent

    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    # Последний safety_check за сегодня по каждому юзеру
    users = db.query(User).filter(User.role == "employee").all()
    result = []

    for user in users:
        last_check = (
            db.query(ScanEvent)
            .filter(
                ScanEvent.user_id == user.id,
                ScanEvent.detected_class == "safety_check",
                ScanEvent.timestamp >= today_start,
            )
            .order_by(ScanEvent.timestamp.desc())
            .first()
        )
        result.append(SafetyStatusOut(
            user_id=user.id,
            username=user.username,
            display_name=user.display_name or user.username,
            passed_today=last_check is not None,
            last_check_at=last_check.timestamp if last_check else None,
        ))

    return result
