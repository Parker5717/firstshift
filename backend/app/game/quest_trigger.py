"""
Quest trigger — автоматическое завершение квестов через CV-детекции.

Вызывается из REST-эндпоинта /api/vision/detect и WS /ws/vision.
Проверяет детекции против активных квестов пользователя, завершает матч.

Использует ту же логику что и ручной POST /api/quests/{slug}/complete,
но без HTTP-слоя — напрямую работает с БД.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Quest, QuestStatus, User, UserQuestProgress
from app.game.xp_engine import add_xp, level_title
from app.game.achievements import check_and_unlock_achievements, record_scan_event

log = logging.getLogger("casper.game.trigger")


def process_cv_detections(
    db: Session,
    user: User,
    objects: list[dict],
    markers: list[dict],
) -> list[dict]:
    """
    Сопоставить CV-детекции с активными квестами пользователя.
    Завершить квест если детекция совпадает с target_class (YOLO)
    или target_marker_id (ArUco).

    Args:
        db:      сессия БД
        user:    текущий пользователь (объект ORM, изменяется in-place)
        objects: список YOLO-детекций из object_detector.detect_objects()
                 каждая содержит ключ "detected_class"
        markers: список ArUco-детекций из marker_detector.detect_markers()
                 каждая содержит ключ "marker_id"

    Returns:
        Список событий для фронтенда. Пустой список если квестов не завершено.
        Каждое событие:
        {
          "type":                       "quest_complete",
          "quest_slug":                 str,
          "quest_title":                str,
          "xp_gained":                  int,
          "new_total_xp":               int,
          "new_level":                  int,
          "leveled_up":                 bool,
          "level_title":                str,
          "newly_unlocked_achievements": list[dict],
        }
    """
    # Загружаем все активные квесты одним запросом (join чтобы не делать N+1)
    active_progress: list[UserQuestProgress] = (
        db.query(UserQuestProgress)
        .filter(
            UserQuestProgress.user_id == user.id,
            UserQuestProgress.status == QuestStatus.ACTIVE.value,
        )
        .join(UserQuestProgress.quest)
        .all()
    )

    if not active_progress:
        return []

    # Что детектировано в этом кадре
    detected_classes: set[str] = {obj["detected_class"] for obj in objects}
    detected_marker_ids: set[int] = {m["marker_id"] for m in markers}

    events: list[dict] = []

    for progress in active_progress:
        quest: Quest = progress.quest
        matched = False

        # Матч по YOLO-классу (задняя камера)
        if quest.target_class and quest.target_class in detected_classes:
            matched = True
            log.debug(
                "YOLO-матч: квест '%s' ← класс '%s'",
                quest.slug, quest.target_class,
            )

        # Матч по ArUco-маркеру (всегда проверяем)
        elif quest.target_marker_id is not None and quest.target_marker_id in detected_marker_ids:
            matched = True
            log.debug(
                "ArUco-матч: квест '%s' ← маркер #%d",
                quest.slug, quest.target_marker_id,
            )

        if not matched:
            continue

        # --- Завершаем квест ---
        progress.status = QuestStatus.COMPLETED.value
        progress.completed_at = datetime.now(timezone.utc)

        # Начисляем XP (обновляет user.total_xp и user.level in-place)
        new_xp, new_level, leveled_up = add_xp(user.total_xp, quest.xp_reward)
        user.total_xp = new_xp
        user.level = new_level

        # Записываем ScanEvent (нужен для анти-чита и ачивок)
        record_scan_event(
            db,
            user_id=user.id,
            detected_class=quest.target_class,
            marker_id=quest.target_marker_id,
            quest_id=quest.id,
        )
        db.flush()  # ScanEvent должен быть виден при проверке ачивок ниже

        # Разблокируем следующие квесты в цепочке
        next_quests: list[Quest] = (
            db.query(Quest)
            .filter(Quest.prerequisite_slug == quest.slug)
            .all()
        )
        for nq in next_quests:
            next_p: UserQuestProgress | None = (
                db.query(UserQuestProgress)
                .filter(
                    UserQuestProgress.user_id == user.id,
                    UserQuestProgress.quest_id == nq.id,
                )
                .first()
            )
            if next_p and next_p.status == QuestStatus.LOCKED.value:
                next_p.status = QuestStatus.AVAILABLE.value
                log.info(
                    "Разблокирован квест '%s' для %s",
                    nq.slug, user.username,
                )

        # Проверяем ачивки
        newly_unlocked: list[dict] = check_and_unlock_achievements(db, user)

        log.info(
            "Квест '%s' автозавершён через CV: %s +%d XP (уровень %d%s)",
            quest.slug, user.username, quest.xp_reward, new_level,
            " ⬆ LEVEL UP!" if leveled_up else "",
        )

        events.append({
            "type":                        "quest_complete",
            "quest_slug":                  quest.slug,
            "quest_title":                 quest.title,
            "xp_gained":                   quest.xp_reward,
            "new_total_xp":                new_xp,
            "new_level":                   new_level,
            "leveled_up":                  leveled_up,
            "level_title":                 level_title(new_level),
            "newly_unlocked_achievements": newly_unlocked,
        })

    if events:
        db.commit()

    return events
