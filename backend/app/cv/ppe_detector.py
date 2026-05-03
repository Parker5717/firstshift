"""
PPE (Personal Protective Equipment) детектор — демо-версия.

Для хакатона используем ArUco маркеры вместо реальных СИЗ:
  ID 10 — каска (распечатай и приложи к голове/лбу)
  ID 11 — жилет (распечатай и приложи к груди)

Это гарантирует стабильную работу на демо без реального снаряжения.
На продакшне: заменить на fine-tuned YOLOv8 модель с классами helmet/vest.
"""

import logging

import cv2
import numpy as np

from app.cv.marker_detector import _DETECTOR

log = logging.getLogger("casper.cv.ppe")

# ID маркеров для демо
HELMET_MARKER_ID = 10
VEST_MARKER_ID   = 11


def detect_ppe(img: np.ndarray) -> dict:
    """
    Проверить наличие СИЗ через ArUco маркеры.

    Маркер ID 10 в верхней части кадра = каска.
    Маркер ID 11 в нижней части кадра = жилет.

    Returns:
        {
          "helmet":  True/False,
          "vest":    True/False,
          "all_ok":  True если оба есть,
          "missing": список недостающих,
          "confidence": float,
          "mode": "aruco_demo",
        }
    """
    if img is None:
        return _empty_result()

    h, w = img.shape[:2]

    try:
        corners, ids, _ = _DETECTOR.detectMarkers(img)
    except Exception as e:
        log.warning("PPE ArUco ошибка: %s", e)
        return _empty_result()

    has_helmet = False
    has_vest   = False

    if ids is not None:
        detected_ids = ids.flatten().tolist()
        log.debug("PPE: обнаружены маркеры %s", detected_ids)

        for marker_corners, marker_id in zip(corners, ids.flatten()):
            mid = int(marker_id)
            # Центр маркера по вертикали
            pts = marker_corners[0]
            cy = float(pts[:, 1].mean()) / h  # 0..1

            if mid == HELMET_MARKER_ID:
                has_helmet = True
                log.info("PPE: каска обнаружена (маркер %d, y=%.2f)", mid, cy)
            elif mid == VEST_MARKER_ID:
                has_vest = True
                log.info("PPE: жилет обнаружен (маркер %d, y=%.2f)", mid, cy)

    missing = []
    if not has_helmet:
        missing.append("helmet")
    if not has_vest:
        missing.append("vest")

    confidence = (int(has_helmet) + int(has_vest)) / 2.0

    return {
        "helmet":     has_helmet,
        "vest":       has_vest,
        "all_ok":     len(missing) == 0,
        "missing":    missing,
        "confidence": confidence,
        "mode":       "aruco_demo",
    }


def _empty_result() -> dict:
    return {
        "helmet":     False,
        "vest":       False,
        "all_ok":     False,
        "missing":    ["helmet", "vest"],
        "confidence": 0.0,
        "mode":       "aruco_demo",
    }
