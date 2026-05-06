"""
Подключение к БД.

Поддерживает SQLite (для локальной разработки) и PostgreSQL (для production).
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=settings.debug,
        future=True,
    )
else:
    engine = create_engine(
        settings.database_url,
        echo=settings.debug,
        future=True,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
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
    когда схема меняется по 5 раз в день. При смене модели проще удалить app.db.
    """
    # Импорт нужен здесь, чтобы все модели зарегистрировались в Base.metadata
    # до вызова create_all. Без этого таблицы просто не создадутся.
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
