"""
ArUco маркер детектор.

Использует OpenCV ArucoDetector с DICT_4X4_50 (маркеры ID 0-49).
Каждый ID соответствует конкретному объекту/зоне в цеху (см. quests.yaml).

Таблица маркеров:
  ID 0 — входная зона (квест first_steps)
  ID 1 — кнопка аварийного стопа (квест emergency_stop)
  ID 2 — рабочий станок (квест machine_intro)
  ID 3 — зона хранения инструмента (квест boss_inspection)
  ID 4-9 — резерв для расширения
"""

import logging

import cv2
import numpy as np

from app.cv.utils import normalize_bbox

log = logging.getLogger("casper.cv.marker")

# Словарь маркеров — загружается один раз
_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

# Параметры детектора — чуть более мягкие для разных условий освещения
_PARAMS = cv2.aruco.DetectorParameters()
_PARAMS.adaptiveThreshWinSizeMin = 3
_PARAMS.adaptiveThreshWinSizeMax = 23
_PARAMS.adaptiveThreshWinSizeStep = 4
_PARAMS.minMarkerPerimeterRate = 0.03
_PARAMS.maxMarkerPerimeterRate = 4.0

_DETECTOR = cv2.aruco.ArucoDetector(_DICT, _PARAMS)

# Человекочитаемые имена маркеров
MARKER_LABELS: dict[int, str] = {
    0: "Входная зона",
    1: "Аварийный стоп",
    2: "Рабочий станок",
    3: "Зона инструмента",
    4: "Огнетушитель",
    5: "Зона B",
    10: "Каска (СИЗ)",
    11: "Жилет (СИЗ)",
}


def detect_markers(img: np.ndarray) -> list[dict]:
    """
    Найти ArUco маркеры на изображении.

    Args:
        img: numpy BGR массив

    Returns:
        Список детекций:
        [
          {
            "marker_id": 1,
            "label": "Аварийный стоп",
            "confidence": 1.0,
            "bbox": {"x": 0.3, "y": 0.2, "w": 0.15, "h": 0.2},
            "corners": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],  # нормализованные
            "color": "#00ff88",
            "type": "marker",
          }
        ]
    """
    if img is None:
        return []

    h, w = img.shape[:2]

    try:
        corners, ids, _ = _DETECTOR.detectMarkers(img)
    except Exception as e:
        log.warning("ArUco ошибка детекции: %s", e)
        return []

    if ids is None or len(ids) == 0:
        return []

    results = []
    for marker_corners, marker_id in zip(corners, ids.flatten()):
        mid = int(marker_id)
        pts = marker_corners[0]  # shape (4, 2)

        # Bbox из углов маркера
        x_coords = pts[:, 0]
        y_coords = pts[:, 1]
        bx = int(x_coords.min())
        by = int(y_coords.min())
        bw = int(x_coords.max()) - bx
        bh = int(y_coords.max()) - by

        # Нормализованные углы для точного рисования в JS
        norm_corners = [[float(pt[0] / w), float(pt[1] / h)] for pt in pts]

        results.append({
            "marker_id": mid,
            "label": MARKER_LABELS.get(mid, f"Маркер #{mid}"),
            "confidence": 1.0,
            "bbox": normalize_bbox(bx, by, bw, bh, w, h),
            "corners": norm_corners,
            "color": "#00ff88",
            "type": "marker",
        })
        log.debug("ArUco: обнаружен маркер ID=%d", mid)

    return results
