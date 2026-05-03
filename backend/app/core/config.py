"""
Конфигурация приложения.

Все настройки загружаются из переменных окружения или .env файла.
Используем pydantic-settings, чтобы получить валидацию типов и автодокументацию.
"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Корень проекта (поднимаемся от backend/app/core/config.py до корня репозитория)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_ROOT = PROJECT_ROOT / "frontend"

# YOLOv8 режим — читаем сразу при импорте модуля
YOLO_MODE: bool = os.environ.get("CASPER_YOLO", "0") == "1"


class Settings(BaseSettings):
    """Все runtime-настройки приложения."""

    # --- Основное ---
    app_name: str = "CASPER AR Assistant"
    app_version: str = "0.1.0"
    debug: bool = True

    # --- HTTP ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- База данных ---
    database_url: str = f"sqlite:///{BACKEND_ROOT / 'casper.db'}"

    # --- Auth ---
    secret_key: str = "casper-hackathon-dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7

    # --- CV ---
    ppe_model_path: Path = BACKEND_ROOT / "models" / "ppe_yolov8.pt"
    equipment_model_path: Path = BACKEND_ROOT / "models" / "equipment_yolov8.pt"

    # YOLOv8 режим — берём из модульной переменной (SET CASPER_YOLO=1)
    yolo_mode: bool = YOLO_MODE

    # --- Пути ---
    quests_yaml_path: Path = BACKEND_ROOT / "app" / "game" / "content" / "quests.yaml"
    achievements_yaml_path: Path = BACKEND_ROOT / "app" / "game" / "content" / "achievements.yaml"
    frontend_static_path: Path = FRONTEND_ROOT

    # --- CORS ---
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
