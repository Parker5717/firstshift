"""
CV утилиты: декодирование изображений из base64, ресайз, конвертация форматов.
"""

import base64
import io
import logging

import cv2
import numpy as np
from PIL import Image

log = logging.getLogger("casper.cv.utils")

# Максимальный размер кадра для обработки (ширина в пикселях).
# Уменьшаем для ускорения: полный 1280px кадр обрабатывается ~200ms,
# 640px — ~50ms. Для ArUco достаточно 640px.
MAX_WIDTH = 640


def base64_to_bgr(b64_string: str) -> np.ndarray | None:
    """
    Декодировать base64 JPEG/PNG → numpy BGR array для OpenCV.
    Принимает строку с или без data URL префикса.
    """
    try:
        # Убираем data:image/jpeg;base64, если есть
        if "," in b64_string:
            b64_string = b64_string.split(",", 1)[1]

        img_bytes = base64.b64decode(b64_string)
        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # Ресайз если нужно
        w, h = pil_img.size
        if w > MAX_WIDTH:
            ratio = MAX_WIDTH / w
            pil_img = pil_img.resize(
                (MAX_WIDTH, int(h * ratio)),
                Image.LANCZOS,
            )

        # PIL RGB → numpy → OpenCV BGR
        arr = np.array(pil_img)
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        return bgr

    except Exception as e:
        log.warning("Ошибка декодирования изображения: %s", e)
        return None


def bgr_to_rgb(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def normalize_bbox(x: int, y: int, w: int, h: int, img_w: int, img_h: int) -> dict:
    """
    Нормализовать bbox к диапазону 0..1 относительно размеров изображения.
    Фронтенд использует нормализованные координаты для рендера на canvas.
    """
    return {
        "x": max(0.0, x / img_w),
        "y": max(0.0, y / img_h),
        "w": min(1.0, w / img_w),
        "h": min(1.0, h / img_h),
    }
