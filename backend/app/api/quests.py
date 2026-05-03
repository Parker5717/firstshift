"""
Quests роутер.

GET  /api/quests              — список всех квестов со статусом для текущего юзера
GET  /api/quests/{slug}       — один квест со статусом
POST /api/quests/{slug}/start — взять квест в работу
POST /api/quests/{slug}/complete — завершить квест (валидация на шаге 7)
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import QuestCompleteOut, QuestListOut, QuestOut, QuestStartOut
from app.db.database import get_db
from app.db.models import Quest, QuestStatus, User, UserQuestProgress
from app.game.xp_engine import add_xp, level_title

log = logging.getLogger("casper.quests")
router = APIRouter()


def _get_user_progress(db: Session, user_id: int) -> dict[int, UserQuestProgress]:
    """Словарь quest_id → UserQuestProgress для быстрого поиска."""
    records = (
        db.query(UserQuestProgress)
        .filter(UserQuestProgress.user_id == user_id)
        .all()
    )
    return {r.quest_id: r for r in records}


def _quest_to_out(quest: Quest, progress: UserQuestProgress | None) -> QuestOut:
    status_val = progress.status if progress else QuestStatus.LOCKED.value
    return QuestOut(
        slug=quest.slug,
        title=quest.title,
        description=quest.description,
        type=quest.type,
        xp_reward=quest.xp_reward,
        difficulty=quest.difficulty,
        story_chapter=quest.story_chapter,
        status=status_val,
        params_json=quest.params_json,
        target_marker_id=quest.target_marker_id,
        target_class=quest.target_class,
    )


@router.get(
    "",
    response_model=QuestListOut,
    summary="Список всех квестов",
)
def list_quests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuestListOut:
    """Все квесты с персональным статусом (locked/available/active/completed/failed)."""
    quests = db.query(Quest).order_by(Quest.story_chapter, Quest.difficulty).all()
    progress_map = _get_user_progress(db, current_user.id)
    out = [_quest_to_out(q, progress_map.get(q.id)) for q in quests]
    return QuestListOut(quests=out, total=len(out))


@router.get(
    "/{slug}",
    response_model=QuestOut,
    summary="Один квест",
)
def get_quest(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuestOut:
    quest = db.query(Quest).filter(Quest.slug == slug).first()
    if not quest:
        raise HTTPException(status_code=404, detail=f"Квест '{slug}' не найден")
    progress = (
        db.query(UserQuestProgress)
        .filter(
            UserQuestProgress.user_id == current_user.id,
            UserQuestProgress.quest_id == quest.id,
        )
        .first()
    )
    return _quest_to_out(quest, progress)


@router.post(
    "/{slug}/start",
    response_model=QuestStartOut,
    summary="Начать квест",
)
def start_quest(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuestStartOut:
    quest = db.query(Quest).filter(Quest.slug == slug).first()
    if not quest:
        raise HTTPException(status_code=404, detail=f"Квест '{slug}' не найден")

    progress = (
        db.query(UserQuestProgress)
        .filter(
            UserQuestProgress.user_id == current_user.id,
            UserQuestProgress.quest_id == quest.id,
        )
        .first()
    )

    if not progress:
        raise HTTPException(status_code=403, detail="Квест недоступен")

    if progress.status == QuestStatus.COMPLETED.value:
        return QuestStartOut(
            slug=slug,
            status=progress.status,
            message="Этот квест уже завершён 🏆",
        )

    if progress.status == QuestStatus.LOCKED.value:
        raise HTTPException(
            status_code=403,
            detail="Квест заблокирован. Сначала выполни предыдущий квест.",
        )

    progress.status = QuestStatus.ACTIVE.value
    progress.started_at = datetime.now(timezone.utc)
    progress.attempts += 1
    db.commit()

    log.info("Квест '%s' начат пользователем %s", slug, current_user.username)
    return QuestStartOut(
        slug=slug,
        status=progress.status,
        message=f"Квест «{quest.title}» начат. Удачи! 🎯",
    )


@router.post(
    "/{slug}/complete",
    response_model=QuestCompleteOut,
    summary="Завершить квест",
    description=(
        "На шаге 2 — упрощённое завершение без CV-валидации (для тестирования). "
        "На шаге 7 добавим проверку через сканирование."
    ),
)
def complete_quest(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuestCompleteOut:
    quest = db.query(Quest).filter(Quest.slug == slug).first()
    if not quest:
        raise HTTPException(status_code=404, detail=f"Квест '{slug}' не найден")

    progress = (
        db.query(UserQuestProgress)
        .filter(
            UserQuestProgress.user_id == current_user.id,
            UserQuestProgress.quest_id == quest.id,
        )
        .first()
    )

    if not progress or progress.status != QuestStatus.ACTIVE.value:
        raise HTTPException(
            status_code=400,
            detail="Квест не активен. Сначала начни его через /start.",
        )

    # Завершаем квест
    progress.status = QuestStatus.COMPLETED.value
    progress.completed_at = datetime.now(timezone.utc)

    # Начисляем XP
    new_xp, new_level, leveled_up = add_xp(current_user.total_xp, quest.xp_reward)
    current_user.total_xp = new_xp
    current_user.level = new_level

    # Записываем ScanEvent (для ачивок)
    from app.game.achievements import check_and_unlock_achievements, record_scan_event
    record_scan_event(
        db,
        user_id=current_user.id,
        detected_class=quest.target_class,
        marker_id=quest.target_marker_id,
        quest_id=quest.id,
    )
    db.flush()  # flush чтобы ScanEvent был виден при проверке ачивок

    # Разблокируем ВСЕ квесты у которых prerequisite = текущий
    next_quests = db.query(Quest).filter(Quest.prerequisite_slug == slug).all()
    for next_quest in next_quests:
        next_progress = (
            db.query(UserQuestProgress)
            .filter(
                UserQuestProgress.user_id == current_user.id,
                UserQuestProgress.quest_id == next_quest.id,
            )
            .first()
        )
        if next_progress and next_progress.status == QuestStatus.LOCKED.value:
            next_progress.status = QuestStatus.AVAILABLE.value
            log.info("Разблокирован квест '%s' для %s", next_quest.slug, current_user.username)

    # Проверяем ачивки
    newly_unlocked = check_and_unlock_achievements(db, current_user)

    db.commit()

    log.info(
        "Квест '%s' завершён: %s +%d XP (итого %d, уровень %d%s)",
        slug, current_user.username, quest.xp_reward, new_xp, new_level,
        " ⬆ LEVEL UP!" if leveled_up else "",
    )

    return QuestCompleteOut(
        slug=slug,
        status=QuestStatus.COMPLETED.value,
        xp_gained=quest.xp_reward,
        new_total_xp=new_xp,
        new_level=new_level,
        leveled_up=leveled_up,
        newly_unlocked_achievements=newly_unlocked,
        message=(
            f"🎉 Уровень {new_level}! Ты теперь «{level_title(new_level)}»!"
            if leveled_up
            else f"✅ Квест завершён! +{quest.xp_reward} XP"
        ),
    )
