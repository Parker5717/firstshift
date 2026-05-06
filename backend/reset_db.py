"""
reset_db.py — безопасная миграция БД без потери данных.

Добавляет новые колонки в существующую SQLite БД если их ещё нет.
Пересеивает квесты и ачивки из YAML.

Запуск (из директории backend/):
    python reset_db.py

Флаги:
    python reset_db.py --hard   # полный сброс: удалить app.db и пересоздать
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("reset_db")

# Добавляем backend/ в путь чтобы импортировать app.*
sys.path.insert(0, str(Path(__file__).parent))


def soft_migrate() -> None:
    """Добавить новые колонки без удаления данных."""
    from app.db.database import engine

    # Список миграций: (таблица, колонка, тип, default)
    migrations = [
        ("users", "password_hash",       "VARCHAR(128)", "NULL"),
        ("users", "role",                "VARCHAR(16)",  "'employee'"),
        ("users", "mentor_id",           "INTEGER",      "NULL"),
        ("users", "privacy_accepted_at", "DATETIME",     "NULL"),
    ]

    with engine.connect() as conn:
        # Получаем список существующих колонок для каждой таблицы
        for table, column, col_type, default in migrations:
            result = conn.exec_driver_sql(f"PRAGMA table_info({table})")
            existing = [row[1] for row in result.fetchall()]

            if column not in existing:
                sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}"
                conn.exec_driver_sql(sql)
                conn.commit()
                log.info("✅ Добавлена колонка: %s.%s", table, column)
            else:
                log.info("⏭  Уже есть: %s.%s", table, column)


def hard_reset() -> None:
    """Полный сброс: удалить БД и пересоздать с нуля."""
    from app.core.config import get_settings
    settings = get_settings()

    db_path = Path(settings.database_url.replace("sqlite:///", ""))
    if db_path.exists():
        db_path.unlink()
        log.info("🗑  Удалена старая БД: %s", db_path)
    else:
        log.info("БД не найдена — создаём с нуля")


def create_tables() -> None:
    """Создать таблицы которых ещё нет (идемпотентно)."""
    from app.db.database import init_db
    init_db()
    log.info("✅ Таблицы созданы / обновлены")


def seed() -> None:
    """Засеять квесты и ачивки из YAML."""
    from app.db.seed import seed_content
    seed_content()
    log.info("✅ Контент засеян")


def main() -> None:
    parser = argparse.ArgumentParser(description="FirstShift DB migration tool")
    parser.add_argument("--hard", action="store_true", help="Полный сброс БД (удаляет все данные!)")
    args = parser.parse_args()

    if args.hard:
        log.warning("⚠️  HARD RESET — все данные будут удалены!")
        confirm = input("Введи 'yes' для подтверждения: ").strip().lower()
        if confirm != "yes":
            log.info("Отменено.")
            return
        hard_reset()
        create_tables()
    else:
        log.info("Мягкая миграция (данные сохраняются)...")
        create_tables()   # создаём новые таблицы если есть
        soft_migrate()    # добавляем новые колонки в существующие

    seed()
    log.info("🚀 Готово! Можно запускать сервер.")


if __name__ == "__main__":
    main()
