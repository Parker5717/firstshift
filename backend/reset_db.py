"""
reset_db.py — инструмент управления БД FirstShift.

Для разработки (SQLite):
    python reset_db.py             # мягкая миграция + пересев контента
    python reset_db.py --hard      # полный сброс БД

Для PostgreSQL (production):
    python reset_db.py --pg        # alembic upgrade head + seed
    python reset_db.py --pg --hard # drop all tables + alembic upgrade head + seed
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("reset_db")

sys.path.insert(0, str(Path(__file__).parent))


def soft_migrate() -> None:
    """Добавить новые колонки в SQLite без потери данных."""
    from app.db.database import engine

    migrations = [
        ("users", "password_hash",       "VARCHAR(128)", "NULL"),
        ("users", "role",                "VARCHAR(16)",  "'employee'"),
        ("users", "mentor_id",           "INTEGER",      "NULL"),
        ("users", "privacy_accepted_at", "DATETIME",     "NULL"),
        ("users", "birth_year",          "INTEGER",      "NULL"),
        ("users", "ui_mode",             "VARCHAR(16)",  "'gamified'"),
        ("users", "tenant_id",           "INTEGER",      "1"),
        ("quests", "tenant_id",          "INTEGER",      "NULL"),
        ("achievements", "tenant_id",    "INTEGER",      "NULL"),
    ]

    with engine.connect() as conn:
        for table, column, col_type, default in migrations:
            result = conn.exec_driver_sql(f"PRAGMA table_info({table})")
            existing = [row[1] for row in result.fetchall()]
            if column not in existing:
                sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}"
                conn.exec_driver_sql(sql)
                conn.commit()
                log.info("Добавлена колонка: %s.%s", table, column)
            else:
                log.info("Уже есть: %s.%s", table, column)

    # Создаём таблицу tenants если её нет (SQLite)
    with engine.connect() as conn:
        result = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tenants'"
        )
        if not result.fetchone():
            conn.exec_driver_sql("""
                CREATE TABLE tenants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(128) NOT NULL,
                    slug VARCHAR(64) NOT NULL UNIQUE,
                    created_at DATETIME NOT NULL
                )
            """)
            conn.commit()
            log.info("Создана таблица tenants")

        # Создаём дефолтный тенант для существующих пользователей
        result = conn.exec_driver_sql("SELECT COUNT(*) FROM tenants")
        if result.fetchone()[0] == 0:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            conn.exec_driver_sql(
                "INSERT INTO tenants (name, slug, created_at) VALUES (?, ?, ?)",
                ("default", "default", now),
            )
            conn.commit()
            tenant_id_result = conn.exec_driver_sql("SELECT id FROM tenants WHERE slug='default'")
            tid = tenant_id_result.fetchone()[0]
            conn.exec_driver_sql(f"UPDATE users SET tenant_id={tid} WHERE tenant_id IS NULL OR tenant_id=0")
            conn.commit()
            log.info("Создан дефолтный тенант (id=%d), все старые пользователи привязаны", tid)


def hard_reset_sqlite() -> None:
    from app.core.config import get_settings
    settings = get_settings()
    db_path = Path(settings.database_url.replace("sqlite:///", ""))
    if db_path.exists():
        db_path.unlink()
        log.info("Удалена старая БД: %s", db_path)


def alembic_upgrade() -> None:
    backend_dir = Path(__file__).parent
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
    )
    if result.returncode != 0:
        log.error("alembic upgrade head завершился с ошибкой")
        sys.exit(1)
    log.info("alembic upgrade head — OK")


def alembic_downgrade_base() -> None:
    backend_dir = Path(__file__).parent
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=backend_dir,
    )


def create_tables() -> None:
    from app.db.database import init_db
    init_db()
    log.info("Таблицы созданы / обновлены")


def seed() -> None:
    from app.db.seed import seed_content
    seed_content()
    log.info("Контент засеян")


def create_sysadmin_user(username: str, password: str) -> None:
    """Создать системного администратора в служебном тенанте __system__."""
    from datetime import datetime, timezone

    from app.api.auth import hash_password
    from app.db.database import SessionLocal
    from app.db.models import Tenant, User

    db = SessionLocal()
    try:
        sys_tenant = db.query(Tenant).filter(Tenant.slug == "__system__").first()
        if not sys_tenant:
            sys_tenant = Tenant(name="System", slug="__system__", created_at=datetime.now(timezone.utc))
            db.add(sys_tenant)
            db.flush()

        existing = db.query(User).filter(
            User.username == username, User.tenant_id == sys_tenant.id
        ).first()
        if existing:
            log.info("Sysadmin '%s' уже существует (id=%d)", username, existing.id)
            return

        from app.db.database import init_db
        init_db()

        user = User(
            tenant_id=sys_tenant.id,
            username=username,
            display_name=username,
            password_hash=hash_password(password),
            role="sysadmin",
        )
        db.add(user)
        db.commit()
        log.info("Sysadmin '%s' создан (id=%d, tenant=__system__)", username, user.id)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="FirstShift DB management tool")
    parser.add_argument("--hard", action="store_true", help="Полный сброс (удаляет все данные!)")
    parser.add_argument("--pg", action="store_true", help="Режим PostgreSQL (использует alembic)")
    parser.add_argument("--create-sysadmin", nargs=2, metavar=("USERNAME", "PASSWORD"),
                        help="Создать системного администратора: --create-sysadmin admin secret")
    args = parser.parse_args()

    if args.create_sysadmin:
        username, password = args.create_sysadmin
        create_tables()
        soft_migrate()
        create_sysadmin_user(username, password)
        log.info("Готово!")
        return

    if args.pg:
        if args.hard:
            log.warning("HARD RESET (PostgreSQL) — все данные будут удалены!")
            confirm = input("Введи 'yes' для подтверждения: ").strip().lower()
            if confirm != "yes":
                log.info("Отменено.")
                return
            alembic_downgrade_base()
        alembic_upgrade()
    else:
        if args.hard:
            log.warning("HARD RESET (SQLite) — все данные будут удалены!")
            confirm = input("Введи 'yes' для подтверждения: ").strip().lower()
            if confirm != "yes":
                log.info("Отменено.")
                return
            hard_reset_sqlite()
        create_tables()
        soft_migrate()

    seed()
    log.info("Готово! Можно запускать сервер.")


if __name__ == "__main__":
    main()
