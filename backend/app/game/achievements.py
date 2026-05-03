"""
Движок ачивок CASPER.

После каждого завершения квеста вызываем check_and_unlock_achievements.
Проверяем условия из achievements.yaml, разблокируем новые и начисляем бонусный XP.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Achievement, ScanEvent, User, UserAchievement, UserQuestProgress, QuestStatus
from app.game.xp_engine import add_xp

log = logging.getLogger("casper.game.achievements")


def check_and_unlock_achievements(
    db: Session,
    user: User,
) -> list[dict]:
    """
    Проверить все незаблокированные ачивки и разблокировать подходящие.

    Returns:
        Список только что разблокированных ачивок (для показа уведомлений).
    """
    all_achievements = db.query(Achievement).all()
    already_unlocked = {
        ua.achievement_id
        for ua in db.query(UserAchievement).filter(UserAchievement.user_id == user.id).all()
    }

    newly_unlocked = []

    for ach in all_achievements:
        if ach.id in already_unlocked:
            continue

        try:
            condition = json.loads(ach.condition_json)
        except Exception:
            continue

        if _check_condition(db, user, condition):
            # Разблокируем
            ua = UserAchievement(
                user_id=user.id,
                achievement_id=ach.id,
                unlocked_at=datetime.now(timezone.utc),
            )
            db.add(ua)

            # Бонусный XP
            if ach.xp_bonus > 0:
                new_xp, new_level, _ = add_xp(user.total_xp, ach.xp_bonus)
                user.total_xp = new_xp
                user.level = new_level

            log.info("Ачивка разблокирована: '%s' для %s (+%d XP)", ach.slug, user.username, ach.xp_bonus)
            newly_unlocked.append({
                "slug":        ach.slug,
                "title":       ach.title,
                "description": ach.description,
                "icon":        ach.icon,
                "xp_bonus":    ach.xp_bonus,
            })

    return newly_unlocked


def _check_condition(db: Session, user: User, condition: dict) -> bool:
    """Проверить одно условие ачивки."""
    ctype = condition.get("type", "")

    if ctype == "quest_completed":
        slug = condition.get("quest_slug", "")
        return _quest_completed(db, user.id, slug)

    if ctype == "quest_completed_count":
        slug = condition.get("quest_slug", "")
        min_count = condition.get("min", 1)
        return _quest_completion_count(db, user.id, slug) >= min_count

    if ctype == "level_reached":
        min_level = condition.get("min", 1)
        return user.level >= min_level

    if ctype == "scan_count":
        min_count = condition.get("min", 1)
        count = db.query(ScanEvent).filter(ScanEvent.user_id == user.id).count()
        return count >= min_count

    if ctype == "unique_scan_count":
        min_count = condition.get("min", 1)
        count = (
            db.query(ScanEvent.detected_class)
            .filter(ScanEvent.user_id == user.id, ScanEvent.detected_class.isnot(None))
            .distinct()
            .count()
        )
        return count >= min_count

    if ctype == "scan_count_class":
        min_count = condition.get("min", 1)
        cls = condition.get("detected_class", "")
        count = (
            db.query(ScanEvent)
            .filter(ScanEvent.user_id == user.id, ScanEvent.detected_class == cls)
            .count()
        )
        return count >= min_count

    log.warning("Неизвестный тип условия ачивки: %s", ctype)
    return False


def _quest_completed(db: Session, user_id: int, quest_slug: str) -> bool:
    from app.db.models import Quest
    quest = db.query(Quest).filter(Quest.slug == quest_slug).first()
    if not quest:
        return False
    progress = (
        db.query(UserQuestProgress)
        .filter(
            UserQuestProgress.user_id == user_id,
            UserQuestProgress.quest_id == quest.id,
            UserQuestProgress.status == QuestStatus.COMPLETED.value,
        )
        .first()
    )
    return progress is not None


def _quest_completion_count(db: Session, user_id: int, quest_slug: str) -> int:
    from app.db.models import Quest
    quest = db.query(Quest).filter(Quest.slug == quest_slug).first()
    if not quest:
        return 0
    progress = (
        db.query(UserQuestProgress)
        .filter(
            UserQuestProgress.user_id == user_id,
            UserQuestProgress.quest_id == quest.id,
            UserQuestProgress.status == QuestStatus.COMPLETED.value,
        )
        .first()
    )
    return 1 if progress else 0


def record_scan_event(
    db: Session,
    user_id: int,
    detected_class: str | None = None,
    marker_id: int | None = None,
    confidence: float | None = None,
    quest_id: int | None = None,
) -> None:
    """Записать событие сканирования для аналитики и ачивок."""
    event = ScanEvent(
        user_id=user_id,
        detected_class=detected_class,
        marker_id=marker_id,
        confidence=confidence,
        quest_id=quest_id,
    )
    db.add(event)
