"""
Главный CV-пайплайн CASPER.

Принимает base64-кадр, запускает детекторы, возвращает унифицированный результат.
Вызывается из REST-эндпоинта POST /api/vision/detect.
"""

import logging
import time

import numpy as np

from app.cv.marker_detector import detect_markers
from app.cv.object_detector import detect_objects
from app.cv.ppe_detector import detect_ppe
from app.cv.utils import base64_to_bgr

log = logging.getLogger("casper.cv.pipeline")


def process_frame(
    b64_image: str,
    run_ppe: bool = False,
    run_objects: bool = True,
) -> dict:
    """
    Обработать один кадр.

    Args:
        b64_image:   base64-строка JPEG/PNG
        run_ppe:     True = запустить PPE-проверку (для фронтальной камеры)
        run_objects: True = запустить YOLOv8 (для задней камеры)

    Returns:
        {
          "markers":        [...],  # ArUco детекции
          "objects":        [...],  # YOLOv8 детекции
          "ppe":            {...},  # PPE-результат (если run_ppe=True)
          "all_detections": [...],  # markers + objects вместе (для AR-оверлея)
          "processing_ms":  int,
        }
    """
    t0 = time.monotonic()

    img: np.ndarray | None = base64_to_bgr(b64_image)

    if img is None:
        return _empty_result(error="Не удалось декодировать изображение")

    # ArUco всегда
    markers = detect_markers(img)

    # YOLOv8 только для задней камеры
    objects = detect_objects(img) if run_objects else []

    # PPE только для фронтальной камеры
    ppe = detect_ppe(img) if run_ppe else None

    processing_ms = int((time.monotonic() - t0) * 1000)

    if markers or objects:
        log.info(
            "CV pipeline: %d маркеров, %d объектов за %dms",
            len(markers), len(objects), processing_ms,
        )

    return {
        "markers":        markers,
        "objects":        objects,
        "ppe":            ppe,
        "all_detections": markers + objects,
        "processing_ms":  processing_ms,
        "error":          None,
    }


def _empty_result(error: str = None) -> dict:
    return {
        "markers":        [],
        "objects":        [],
        "ppe":            None,
        "all_detections": [],
        "processing_ms":  0,
        "error":          error,
    }
