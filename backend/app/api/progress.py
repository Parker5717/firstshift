"""
Progress роутер.

GET /api/progress/achievements  — список всех ачивок с флагом разблокировки
GET /api/progress/stats         — сводная статистика пользователя
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import Achievement, ScanEvent, User, UserAchievement, UserQuestProgress, QuestStatus

log = logging.getLogger("casper.api.progress")
router = APIRouter()


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


@router.post("/safety_check", summary="Записать прохождение Safety Check")
def record_safety_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Вызывается при успешном прохождении Safety Check.
    Записывает ScanEvent с detected_class='safety_check' для ачивки.
    """
    from app.game.achievements import check_and_unlock_achievements, record_scan_event
    record_scan_event(db, user_id=current_user.id, detected_class="safety_check")
    db.flush()
    newly_unlocked = check_and_unlock_achievements(db, current_user)
    db.commit()
    log.info("Safety Check пройден: %s", current_user.username)
    return {
        "recorded": True,
        "newly_unlocked_achievements": newly_unlocked,
    }
@router.get("/stats", summary="Stats")
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

    return {
        "username":             current_user.username,
        "level":                current_user.level,
        "total_xp":             current_user.total_xp,
        "quests_completed":     quests_completed,
        "scans_total":          scans_total,
        "achievements_unlocked": achievements_unlocked,
        "current_streak":       current_user.current_streak,
    }
