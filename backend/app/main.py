"""
CASPER AR Assistant — точка входа FastAPI.

Запуск (из директории backend/):
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

После запуска:
    http://localhost:8000/         — заглушка (потом отдадим фронт)
    http://localhost:8000/health   — проверка живости
    http://localhost:8000/docs     — Swagger UI с автодокументацией
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("casper")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan-хук FastAPI: код до `yield` выполняется на старте,
    после `yield` — на остановке приложения.
    """
    log.info("Starting %s v%s", settings.app_name, settings.app_version)
    log.info("Initializing database at %s", settings.database_url)
    init_db()
    log.info("Database ready")
    from app.db.seed import seed_content
    seed_content()
    log.info("Content seeded")

    # YOLOv8 режим
    if settings.yolo_mode:
        log.info("🤖 YOLOv8 режим ВКЛЮЧЁН")
        from app.cv.object_detector import _load_model
        _load_model()
    else:
        log.info("📍 Режим: ArUco markers | Для YOLOv8: SET CASPER_YOLO=1 && uvicorn ...")

    yield
    log.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AR-помощник для адаптации молодых сотрудников на производстве. "
        "Хакатон «Цифровой вызов» от Casper AI."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Базовые эндпоинты (на шаге 1 их два — корень и health)
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health() -> JSONResponse:
    """Проверка живости и статус CV-режима."""
    from app.cv.object_detector import _model_available
    return JSONResponse(
        status_code=200,
        content={
            "status":      "healthy",
            "app":         settings.app_name,
            "version":     settings.app_version,
            "cv_mode":     "yolov8+aruco" if settings.yolo_mode else "aruco_only",
            "yolo_active": bool(_model_available) if settings.yolo_mode else False,
            "debug":       settings.debug,
        },
    )


# Роутеры API
from app.api import auth, quests, users, vision, markers, progress
from app.api import vision_ws

app.include_router(auth.router,       prefix="/api/auth",     tags=["auth"])
app.include_router(users.router,      prefix="/api/users",    tags=["users"])
app.include_router(quests.router,     prefix="/api/quests",   tags=["quests"])
app.include_router(vision.router,     prefix="/api/vision",   tags=["vision"])
app.include_router(markers.router,    prefix="/api/markers",  tags=["markers"])
app.include_router(progress.router,   prefix="/api/progress", tags=["progress"])
app.include_router(vision_ws.router,  prefix="/ws",           tags=["websocket"])

# Статика фронтенда
_static = settings.frontend_static_path / "static"
if _static.exists():
    app.mount("/static", StaticFiles(directory=str(_static)), name="static")


@app.get("/", include_in_schema=False)
async def serve_index() -> FileResponse:
    """Login-страница."""
    return FileResponse(str(settings.frontend_static_path / "index.html"))


@app.get("/app", include_in_schema=False)
async def serve_app() -> FileResponse:
    """Главный экран с камерой."""
    return FileResponse(str(settings.frontend_static_path / "app.html"))


@app.get("/markers", include_in_schema=False)
async def serve_markers() -> FileResponse:
    """Страница с печатными ArUco маркерами."""
    return FileResponse(str(settings.frontend_static_path / "markers.html"))


@app.get("/safety", include_in_schema=False)
async def serve_safety() -> FileResponse:
    """Safety Check экран — проверка СИЗ."""
    return FileResponse(str(settings.frontend_static_path / "safety.html"))


@app.get("/profile", include_in_schema=False)
async def serve_profile() -> FileResponse:
    """Страница профиля и лидерборда."""
    return FileResponse(str(settings.frontend_static_path / "profile.html"))


@app.get("/encyclopedia", include_in_schema=False)
async def serve_encyclopedia() -> FileResponse:
    """Энциклопедия объектов цеха."""
    return FileResponse(str(settings.frontend_static_path / "encyclopedia.html"))
