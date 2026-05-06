"""
Progress роутер.

GET  /api/progress/achievements  — список всех ачивок с флагом разблокировки
GET  /api/progress/stats         — сводная статистика пользователя
POST /api/progress/safety_check  — записать результат Safety Check
GET  /api/progress/safety_history — история Safety Check текущего пользователя
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import (
    Achievement, QuestStatus, SafetyCheck,
    ScanEvent, User, UserAchievement, UserQuestProgress,
)

log = logging.getLogger("firstshift.progress")
router = APIRouter()


# ── Схемы ────────────────────────────────────────────────────────────────────

class SafetyCheckIn(BaseModel):
    helmet: bool = False
    vest: bool   = False
    goggles: bool = False
    client_id: str | None = None  # UUID от фронта для дедупликации


# ── Эндпоинты ────────────────────────────────────────────────────────────────

@router.get("/achievements", summary="Все ачивки с флагом разблокировки")
def get_achievements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    all_achievements = db.query(Achievement).all()
    unlocked_map = {
        ua.achievement_id: ua.unlocked_at
        for ua in db.query(UserAchievement)
        .filter(UserAchievement.user_id == current_user.id)
        .all()
    }
    result = []
    for ach in all_achievements:
        unlocked_at = unlocked_map.get(ach.id)
        result.append({
            "slug":        ach.slug,
            "title":       ach.title,
            "description": ach.description,
            "icon":        ach.icon,
            "xp_bonus":    ach.xp_bonus,
            "unlocked":    unlocked_at is not None,
            "unlocked_at": unlocked_at.isoformat() if unlocked_at else None,
        })
    return result


@router.post("/safety_check", summary="Записать результат Safety Check")
def record_safety_check(
    payload: SafetyCheckIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Записывает результат Safety Check в таблицу safety_checks.
    Дедуплицирует по client_id (для офлайн-синхронизации).
    Также пишет ScanEvent для ачивок (обратная совместимость).
    """
    if current_user.role in ("mentor", "hr", "admin"):
        return {"recorded": False, "bypassed": True, "message": "Safety Check не требуется для данной роли"}

    passed = payload.helmet and payload.vest
    missing = []
    if not payload.helmet: missing.append("helmet")
    if not payload.vest:   missing.append("vest")
    if not payload.goggles: missing.append("goggles")

    client_id = payload.client_id or str(uuid.uuid4())

    # Дедупликация — если запись с таким client_id уже есть, игнорируем
    existing = (
        db.query(SafetyCheck)
        .filter(
            SafetyCheck.user_id == current_user.id,
            SafetyCheck.client_id == client_id,
        )
        .first()
    )
    if existing:
        log.info("Safety Check дубликат (client_id=%s), пропускаем", client_id)
        return {"recorded": False, "duplicate": True, "newly_unlocked_achievements": []}

    # Записываем в safety_checks
    check = SafetyCheck(
        user_id=current_user.id,
        passed=passed,
        helmet=payload.helmet,
        vest=payload.vest,
        goggles=payload.goggles,
        missing_items=json.dumps(missing),
        client_id=client_id,
    )
    db.add(check)
    db.flush()

    # ScanEvent для ачивки "прошёл Safety Check"
    from app.game.achievements import check_and_unlock_achievements, record_scan_event
    record_scan_event(db, user_id=current_user.id, detected_class="safety_check")
    db.flush()

    newly_unlocked = check_and_unlock_achievements(db, current_user)
    db.commit()

    log.info(
        "Safety Check: %s | passed=%s | helmet=%s vest=%s goggles=%s",
        current_user.username, passed, payload.helmet, payload.vest, payload.goggles,
    )

    return {
        "recorded": True,
        "passed": passed,
        "missing": missing,
        "newly_unlocked_achievements": newly_unlocked,
    }


@router.get("/safety_history", summary="История Safety Check текущего пользователя")
def safety_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    checks = (
        db.query(SafetyCheck)
        .filter(SafetyCheck.user_id == current_user.id)
        .order_by(SafetyCheck.timestamp.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "timestamp": c.timestamp.isoformat(),
            "passed":    c.passed,
            "helmet":    c.helmet,
            "vest":      c.vest,
            "goggles":   c.goggles,
            "missing":   json.loads(c.missing_items or "[]"),
        }
        for c in checks
    ]


@router.get("/scanned_objects", summary="Список отсканированных объектов энциклопедии")
def get_scanned_objects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Возвращает список ID объектов которые пользователь уже отсканировал.
    Используется энциклопедией для разблокировки карточек.

    Маппинг marker_id → encyclopedia object id:
      0 → marker_0, 1 → marker_1, 2 → marker_2,
      3 → marker_3, 4 → marker_4,
      10 → ppe_helmet, 11 → ppe_vest
    """
    MARKER_TO_ENC = {
        0: 'marker_0', 1: 'marker_1', 2: 'marker_2',
        3: 'marker_3', 4: 'marker_4',
        10: 'ppe_helmet', 11: 'ppe_vest',
    }
    CLASS_TO_ENC = {
        'fire_extinguisher': 'marker_4',
        'safety_check':      'ppe_helmet',  # safety check открывает оба СИЗ
    }

    scanned = set()

    # По ArUco маркерам
    marker_events = (
        db.query(ScanEvent.marker_id)
        .filter(
            ScanEvent.user_id == current_user.id,
            ScanEvent.marker_id.isnot(None),
        )
        .distinct()
        .all()
    )
    for (mid,) in marker_events:
        if mid in MARKER_TO_ENC:
            scanned.add(MARKER_TO_ENC[mid])

    # По YOLO классам
    class_events = (
        db.query(ScanEvent.detected_class)
        .filter(
            ScanEvent.user_id == current_user.id,
            ScanEvent.detected_class.isnot(None),
        )
        .distinct()
        .all()
    )
    for (cls,) in class_events:
        if cls in CLASS_TO_ENC:
            scanned.add(CLASS_TO_ENC[cls])

    # Safety Check открывает СИЗ объекты
    safety_count = (
        db.query(SafetyCheck)
        .filter(SafetyCheck.user_id == current_user.id)
        .count()
    )
    if safety_count > 0:
        scanned.add('ppe_helmet')
        scanned.add('ppe_vest')

    return {"scanned": list(scanned), "total": len(MARKER_TO_ENC) + 1}


@router.get("/stats", summary="Сводная статистика пользователя")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    quests_completed = (
        db.query(UserQuestProgress)
        .filter(
            UserQuestProgress.user_id == current_user.id,
            UserQuestProgress.status == QuestStatus.COMPLETED.value,
        )
        .count()
    )
    scans_total = (
        db.query(ScanEvent)
        .filter(ScanEvent.user_id == current_user.id)
        .count()
    )
    achievements_unlocked = (
        db.query(UserAchievement)
        .filter(UserAchievement.user_id == current_user.id)
        .count()
    )
    safety_total = (
        db.query(SafetyCheck)
        .filter(SafetyCheck.user_id == current_user.id)
        .count()
    )

    return {
        "username":              current_user.username,
        "level":                 current_user.level,
        "total_xp":              current_user.total_xp,
        "quests_completed":      quests_completed,
        "scans_total":           scans_total,
        "achievements_unlocked": achievements_unlocked,
        "current_streak":        current_user.current_streak,
        "safety_checks_total":   safety_total,
    }
