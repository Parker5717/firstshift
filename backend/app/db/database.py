"""
Подключение к БД.

Используем SQLAlchemy 2.x с DeclarativeBase. SQLite выбран как zero-config
вариант для хакатона — для прода менять `database_url` в config.py.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


# `check_same_thread=False` нужен только для SQLite, чтобы FastAPI мог использовать
# одну сессию из разных тредов воркера. Для PostgreSQL/MySQL аргумент игнорируется.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    echo=settings.debug,  # SQL-логи только в debug-режиме
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # чтобы можно было читать поля после commit без лишнего SELECT
)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей. Наследовать в models.py."""
    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency: открывает сессию на время запроса, закрывает после.

    Пример использования в эндпоинте:
        @router.get("/users/{id}")
        def read_user(id: int, db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Создаёт все таблицы из metadata.
    Вызывается один раз при старте приложения (см. main.py).

    На хакатоне сознательно не используем Alembic — миграции это лишние танцы,
    когда схема меняется по 5 раз в день. При смене модели проще удалить casper.db.
    """
    # Импорт нужен здесь, чтобы все модели зарегистрировались в Base.metadata
    # до вызова create_all. Без этого таблицы просто не создадутся.
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
