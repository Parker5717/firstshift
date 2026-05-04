"""
Admin роутер — эндпоинты для HR, наставников и администраторов.

Доступ по ролям:
  employee:  нет доступа
  mentor:    /api/admin/mentor/* (только свои подопечные)
  hr, admin: /api/admin/users/*, /api/admin/safety/*
  admin:     + PATCH role, PATCH mentor
"""

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.database import get_db
from app.db.models import Quest, QuestStatus, ScanEvent, User, UserQuestProgress
from app.game.xp_engine import level_title

log = logging.getLogger("firstshift.admin")
router = APIRouter()

VALID_ROLES = {"employee", "mentor", "hr", "admin"}


# ── Схемы ────────────────────────────────────────────────────────────────────

class EmployeeOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    mentor_id: int | None
    mentor_name: str | None
    level: int
    level_title: str
    total_xp: int
    quests_completed: int
    quests_total: int
    completion_pct: float
    created_at: datetime
    last_active_at: datetime
    model_config = {"from_attributes": True}


class QuestProgressOut(BaseModel):
    slug: str
    title: str
    type: str
    xp_reward: int
    status: str
    completed_at: datetime | None


class RolePatchIn(BaseModel):
    role: str


class MentorPatchIn(BaseModel):
    mentor_id: int | None


class SafetyStatusOut(BaseModel):
    user_id: int
    username: str
    display_name: str
    passed_today: bool
    last_check_at: datetime | None = None


# ── Хелперы ───────────────────────────────────────────────────────────────────

def _employee_out(user: User, db: Session) -> EmployeeOut:
    total = db.query(UserQuestProgress).filter(UserQuestProgress.user_id == user.id).count()
    completed = db.query(UserQuestProgress).filter(
        UserQuestProgress.user_id == user.id,
        UserQuestProgress.status == QuestStatus.COMPLETED.value,
    ).count()

    mentor_name = None
    if user.mentor_id:
        mentor = db.query(User).filter(User.id == user.mentor_id).first()
        if mentor:
            mentor_name = mentor.display_name or mentor.username

    return EmployeeOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
        role=user.role,
        mentor_id=user.mentor_id,
        mentor_name=mentor_name,
        level=user.level,
        level_title=level_title(user.level),
        total_xp=user.total_xp,
        quests_completed=completed,
        quests_total=total,
        completion_pct=round(completed / total * 100, 1) if total else 0.0,
        created_at=user.created_at,
        last_active_at=user.last_active_at,
    )


# ── HR / Admin: список сотрудников ───────────────────────────────────────────

@router.get("/users", response_model=list[EmployeeOut], summary="Список сотрудников")
def list_employees(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("hr", "admin")),
) -> list[EmployeeOut]:
    users = db.query(User).order_by(User.total_xp.desc()).all()
    return [_employee_out(u, db) for u in users]


@router.get("/users/{user_id}", response_model=EmployeeOut, summary="Детали сотрудника")
def get_employee(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("hr", "admin")),
) -> EmployeeOut:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return _employee_out(user, db)


@router.get(
    "/users/{user_id}/quests",
    response_model=list[QuestProgressOut],
    summary="Прогресс по квестам сотрудника",
)
def get_employee_quests(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("hr", "admin", "mentor")),
) -> list[QuestProgressOut]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    progress = (
        db.query(UserQuestProgress)
        .filter(UserQuestProgress.user_id == user_id)
        .join(UserQuestProgress.quest)
        .order_by(Quest.story_chapter, Quest.difficulty)
        .all()
    )
    return [
        QuestProgressOut(
            slug=p.quest.slug,
            title=p.quest.title,
            type=p.quest.type,
            xp_reward=p.quest.xp_reward,
            status=p.status,
            completed_at=p.completed_at,
        )
        for p in progress
    ]


# ── Admin: смена роли и наставника ───────────────────────────────────────────

@router.patch("/users/{user_id}/role", response_model=dict, summary="Сменить роль (admin)")
def set_role(
    user_id: int,
    body: RolePatchIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
) -> dict:
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Допустимые роли: {', '.join(VALID_ROLES)}")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя менять собственную роль")

    old_role = user.role
    user.role = body.role
    db.commit()
    log.info("Admin %s: роль %s → %s для %s", admin.username, old_role, body.role, user.username)
    return {"ok": True, "user_id": user_id, "role": body.role}


@router.patch("/users/{user_id}/mentor", response_model=dict, summary="Назначить наставника (admin/hr)")
def set_mentor(
    user_id: int,
    body: MentorPatchIn,
    db: Session = Depends(get_db),
    current: User = Depends(require_role("hr", "admin")),
) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if body.mentor_id is not None:
        mentor = db.query(User).filter(User.id == body.mentor_id).first()
        if not mentor:
            raise HTTPException(status_code=404, detail="Наставник не найден")
        if mentor.role not in ("mentor", "hr", "admin"):
            raise HTTPException(status_code=400, detail="Наставник должен иметь роль mentor/hr/admin")

    user.mentor_id = body.mentor_id
    db.commit()
    log.info("%s: наставник для %s → %s", current.username, user.username, body.mentor_id)
    return {"ok": True, "user_id": user_id, "mentor_id": body.mentor_id}


# ── Mentor: мои подопечные ────────────────────────────────────────────────────

@router.get("/mentor/employees", response_model=list[EmployeeOut], summary="Мои подопечные")
def my_mentees(
    db: Session = Depends(get_db),
    current: User = Depends(require_role("mentor", "hr", "admin")),
) -> list[EmployeeOut]:
    mentees = db.query(User).filter(User.mentor_id == current.id).all()
    return [_employee_out(u, db) for u in mentees]


# ── Safety Check ──────────────────────────────────────────────────────────────

@router.get("/safety/today", response_model=list[SafetyStatusOut], summary="Safety Check сегодня")
def safety_today(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("hr", "admin")),
) -> list[SafetyStatusOut]:
    from app.db.models import SafetyCheck
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    users = db.query(User).filter(User.role == "employee").all()
    result = []
    for user in users:
        last_check = (
            db.query(SafetyCheck)
            .filter(
                SafetyCheck.user_id == user.id,
                SafetyCheck.timestamp >= today_start,
            )
            .order_by(SafetyCheck.timestamp.desc())
            .first()
        )
        result.append(SafetyStatusOut(
            user_id=user.id,
            username=user.username,
            display_name=user.display_name or user.username,
            passed_today=last_check is not None and last_check.passed,
            last_check_at=last_check.timestamp if last_check else None,
        ))
    return result
