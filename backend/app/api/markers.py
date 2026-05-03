"""
Markers роутер — генерация ArUco маркеров для печати.

GET /api/markers/{id}/image  — PNG изображение маркера
GET /api/markers/info        — список маркеров с описанием
"""

import io
import logging

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.cv.marker_detector import MARKER_LABELS

log = logging.getLogger("casper.api.markers")
router = APIRouter()

_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


@router.get("/info", summary="Список маркеров")
def markers_info() -> list[dict]:
    """Возвращает список маркеров с ID, описанием и квестом."""
    return [
        {"id": 0, "label": MARKER_LABELS[0], "quest": "first_steps",    "icon": "🚪"},
        {"id": 1, "label": MARKER_LABELS[1], "quest": "emergency_stop",  "icon": "🛑"},
        {"id": 2, "label": MARKER_LABELS[2], "quest": "machine_intro",   "icon": "⚙️"},
        {"id": 3, "label": MARKER_LABELS[3], "quest": "boss_inspection", "icon": "🔧"},
    ]


@router.get("/{marker_id}/image", summary="PNG изображение маркера")
def get_marker_image(marker_id: int) -> Response:
    """
    Генерирует и возвращает PNG изображение ArUco маркера.
    Размер: 300x300 пикселей с белой рамкой для печати.
    """
    if marker_id < 0 or marker_id > 49:
        raise HTTPException(status_code=400, detail="ID маркера должен быть от 0 до 49")

    # Генерируем маркер 280x280 + белая рамка 10px
    marker_size = 280
    border = 10
    total = marker_size + border * 2

    # Сам маркер
    marker_img = cv2.aruco.generateImageMarker(_DICT, marker_id, marker_size)

    # Добавляем белую рамку
    canvas = np.ones((total, total), dtype=np.uint8) * 255
    canvas[border:border + marker_size, border:border + marker_size] = marker_img

    # Кодируем в PNG
    success, buf = cv2.imencode('.png', canvas)
    if not success:
        raise HTTPException(status_code=500, detail="Ошибка генерации маркера")

    return Response(
        content=buf.tobytes(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )
