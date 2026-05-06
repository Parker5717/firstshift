"""
ArUco маркер детектор.

Использует OpenCV ArucoDetector с DICT_4X4_50 (маркеры ID 0-49).

Таблица маркеров:
  ID 0 — входная зона       (квест first_steps)
  ID 1 — кнопка аварийного стопа (квест emergency_stop)
  ID 2 — рабочий станок     (квест machine_intro)
  ID 3 — зона хранения      (квест boss_inspection)
  ID 4 — огнетушитель       (квест find_extinguisher)
  ID 10 — каска (СИЗ)
  ID 11 — жилет (СИЗ)
"""

import logging

import cv2
import numpy as np

from app.cv.utils import normalize_bbox

log = logging.getLogger("firstshift.cv.marker")

_DICT   = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
_PARAMS = cv2.aruco.DetectorParameters()
_PARAMS.adaptiveThreshWinSizeMin  = 3
_PARAMS.adaptiveThreshWinSizeMax  = 23
_PARAMS.adaptiveThreshWinSizeStep = 4
_PARAMS.minMarkerPerimeterRate    = 0.03
_PARAMS.maxMarkerPerimeterRate    = 4.0
_DETECTOR = cv2.aruco.ArucoDetector(_DICT, _PARAMS)

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

# Оценка расстояния: маркер ~10 см, фокусное расстояние телефона ~800 px
_MARKER_SIZE_M = 0.10
_FOCAL_PX      = 800.0


def detect_markers(img: np.ndarray) -> list[dict]:
    """
    Найти ArUco маркеры на изображении.

    Returns:
        Список детекций с полями:
          marker_id, label, confidence, bbox, corners, color, type,
          distance_cm (оценка в см),
          direction_x (-1=лево .. +1=право),
          direction_y (-1=верх .. +1=низ)
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
        pts = marker_corners[0]  # (4, 2)

        x_coords = pts[:, 0]
        y_coords = pts[:, 1]
        bx = int(x_coords.min())
        by = int(y_coords.min())
        bw = int(x_coords.max()) - bx
        bh = int(y_coords.max()) - by

        norm_corners = [[float(pt[0] / w), float(pt[1] / h)] for pt in pts]

        # Оценка расстояния по размеру маркера в пикселях
        marker_px = max(bw, bh)
        distance_cm = int((_FOCAL_PX * _MARKER_SIZE_M) / marker_px * 100) if marker_px > 0 else None

        # Направление: центр маркера относительно центра кадра
        cx_px = bx + bw / 2
        cy_px = by + bh / 2
        direction_x = round((cx_px / w - 0.5) * 2, 3)
        direction_y = round((cy_px / h - 0.5) * 2, 3)

        results.append({
            "marker_id":   mid,
            "label":       MARKER_LABELS.get(mid, f"Маркер #{mid}"),
            "confidence":  1.0,
            "bbox":        normalize_bbox(bx, by, bw, bh, w, h),
            "corners":     norm_corners,
            "color":       "#00ff88",
            "type":        "marker",
            "distance_cm": distance_cm,
            "direction_x": direction_x,
            "direction_y": direction_y,
        })
        log.debug("ArUco: ID=%d dist=%scm", mid, distance_cm)

    return results
