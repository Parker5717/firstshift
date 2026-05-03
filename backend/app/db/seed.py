"""
Сидер контента: квесты и ачивки из YAML → таблицы quests и achievements.

Принципы:
- Идемпотентность: повторный запуск не дублирует данные (upsert по slug).
- Источник истины — YAML-файлы. Если YAML изменился — при следующем старте
  приложения изменения применятся автоматически.
- При добавлении нового квеста в YAML он появится в БД без удаления casper.db.
"""

import json
import logging

import yaml
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import SessionLocal
from app.db.models import Achievement, Quest

log = logging.getLogger("casper.seed")
settings = get_settings()


def _upsert_quest(db: Session, data: dict) -> Quest:
    """Создать или обновить квест по slug."""
    slug = data["slug"]
    quest = db.query(Quest).filter(Quest.slug == slug).first()

    params = data.get("params_json", "{}")
    # YAML может вернуть dict если params_json не строка — сериализуем обратно
    if isinstance(params, dict):
        params = json.dumps(params, ensure_ascii=False)

    fields = dict(
        title=data["title"],
        description=data["description"].strip(),
        type=data["type"],
        target_class=data.get("target_class"),
        target_marker_id=data.get("target_marker_id"),
        xp_reward=data.get("xp_reward", 50),
        prerequisite_slug=data.get("prerequisite_slug"),
        story_chapter=data.get("story_chapter", 1),
        difficulty=data.get("difficulty", 1),
        params_json=params,
    )

    if quest is None:
        quest = Quest(slug=slug, **fields)
        db.add(quest)
        log.debug("  + quest '%s' создан", slug)
    else:
        for k, v in fields.items():
            setattr(quest, k, v)
        log.debug("  ~ quest '%s' обновлён", slug)

    return quest


def _upsert_achievement(db: Session, data: dict) -> Achievement:
    """Создать или обновить ачивку по slug."""
    slug = data["slug"]
    ach = db.query(Achievement).filter(Achievement.slug == slug).first()

    condition = data.get("condition_json", "{}")
    if isinstance(condition, dict):
        condition = json.dumps(condition, ensure_ascii=False)

    fields = dict(
        title=data["title"],
        description=data["description"].strip(),
        icon=data.get("icon", "trophy"),
        xp_bonus=data.get("xp_bonus", 0),
        condition_json=condition,
    )

    if ach is None:
        ach = Achievement(slug=slug, **fields)
        db.add(ach)
        log.debug("  + achievement '%s' создана", slug)
    else:
        for k, v in fields.items():
            setattr(ach, k, v)
        log.debug("  ~ achievement '%s' обновлена", slug)

    return ach


def seed_content() -> None:
    """
    Главная функция сидинга. Вызывается из lifespan в main.py.
    Загружает quests.yaml и achievements.yaml в БД.
    """
    db: Session = SessionLocal()
    try:
        _seed_quests(db)
        _seed_achievements(db)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Ошибка при сидинге контента")
        raise
    finally:
        db.close()


def _seed_quests(db: Session) -> None:
    path = settings.quests_yaml_path
    if not path.exists():
        log.warning("quests.yaml не найден: %s", path)
        return

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    quests_data = data.get("quests", [])
    log.info("Сидинг квестов: %d записей из %s", len(quests_data), path.name)
    for item in quests_data:
        _upsert_quest(db, item)


def _seed_achievements(db: Session) -> None:
    path = settings.achievements_yaml_path
    if not path.exists():
        log.warning("achievements.yaml не найден: %s", path)
        return

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    ach_data = data.get("achievements", [])
    log.info("Сидинг ачивок: %d записей из %s", len(ach_data), path.name)
    for item in ach_data:
        _upsert_achievement(db, item)
