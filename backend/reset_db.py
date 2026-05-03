"""
Утилита очистки базы данных CASPER.

Использование:
    python reset_db.py          — полная очистка (удаляет и пересоздаёт БД)
    python reset_db.py --users  — только очистить пользователей и прогресс
    python reset_db.py --keep   — удалить юзеров но сохранить квесты и ачивки
"""

import argparse
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings
from app.db.database import engine, SessionLocal, init_db
from app.db.models import User, UserQuestProgress, UserAchievement, ScanEvent

settings = get_settings()


def reset_full():
    """Полный сброс: удалить БД и пересоздать с нуля."""
    db_path = Path(str(settings.database_url).replace("sqlite:///", ""))
    if db_path.exists():
        db_path.unlink()
        print(f"✓ Удалена БД: {db_path}")
    init_db()
    from app.db.seed import seed_content
    seed_content()
    print("✓ БД пересоздана и заполнена контентом")


def reset_users():
    """Удалить всех пользователей и связанные данные."""
    db = SessionLocal()
    try:
        deleted = db.query(ScanEvent).delete()
        print(f"  ScanEvents удалено: {deleted}")
        deleted = db.query(UserAchievement).delete()
        print(f"  UserAchievements удалено: {deleted}")
        deleted = db.query(UserQuestProgress).delete()
        print(f"  UserQuestProgress удалено: {deleted}")
        deleted = db.query(User).delete()
        print(f"  Users удалено: {deleted}")
        db.commit()
        print("✓ Все пользователи и прогресс очищены")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Сброс БД CASPER AR Assistant")
    parser.add_argument("--users", action="store_true", help="Только очистить пользователей")
    args = parser.parse_args()

    if args.users:
        print("Очищаю пользователей...")
        reset_users()
    else:
        print("Полный сброс БД...")
        reset_full()

    print("Готово!")
