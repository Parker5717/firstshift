"""
Детектор объектов на базе YOLOv8n (ultralytics).

Модель загружается лениво при первом запросе (не блокирует старт приложения).
Если ultralytics или torch не установлены — возвращает пустой список.

Для хакатона используем YOLOv8n pretrained on COCO.
Маппинг COCO → наши квест-объекты в DEMO_CLASS_MAP ниже.
"""

import logging

import numpy as np

from app.cv.utils import normalize_bbox

log = logging.getLogger("casper.cv.objects")

# --- Маппинг COCO классов → квест-объекты ---
# В демо-режиме некоторые стандартные объекты переименованы в производственные.
# Это позволяет показать работу без кастомно обученной модели.
DEMO_CLASS_MAP: dict[str, str] = {
    "bottle":       "fire_extinguisher",  # красная бутылка ≈ огнетушитель
    "fire hydrant": "fire_extinguisher",  # если вдруг есть
    "scissors":     "cutting_tool",
    "chair":        "workstation",
    "laptop":       "control_panel",
    "keyboard":     "control_panel",
    "cell phone":   "handheld_device",
    "person":       "person",
}

# COCO классы которые нас интересуют (остальные игнорируем)
RELEVANT_CLASSES = set(DEMO_CLASS_MAP.keys())

# Порог уверенности
CONFIDENCE_THRESHOLD = 0.45

# Цвета по типу объекта
OBJECT_COLORS: dict[str, str] = {
    "fire_extinguisher": "#ff3355",
    "person":            "#00aaff",
    "default":           "#ffaa00",
}

# Глобальный кэш модели (загружается один раз)
_model = None
_model_available = None  # None = ещё не проверяли, True/False = проверили


def _load_model():
    """Загрузить YOLOv8n при первом вызове. Вернуть False если не доступна."""
    global _model, _model_available

    if _model_available is not None:
        return _model_available

    try:
        from ultralytics import YOLO
        log.info("Загружаю YOLOv8n...")
        _model = YOLO("yolov8n.pt")  # автозагрузка ~6MB если нет в кэше
        _model_available = True
        log.info("YOLOv8n загружена успешно")
    except ImportError:
        log.warning("ultralytics не установлен — объектная детекция отключена")
        _model_available = False
    except Exception as e:
        log.warning("Не удалось загрузить YOLOv8n: %s", e)
        _model_available = False

    return _model_available


def detect_objects(img: np.ndarray) -> list[dict]:
    """
    Найти объекты на изображении через YOLOv8n.

    Args:
        img: numpy BGR массив

    Returns:
        Список детекций в том же формате что marker_detector.
    """
    if img is None:
        return []

    if not _load_model():
        return []

    h, w = img.shape[:2]
    results = []

    try:
        preds = _model(img, verbose=False, conf=CONFIDENCE_THRESHOLD)

        for result in preds:
            for box in result.boxes:
                cls_name = result.names[int(box.cls[0])]
                if cls_name not in RELEVANT_CLASSES:
                    continue

                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                bx, by = x1, y1
                bw, bh = x2 - x1, y2 - y1

                quest_class = DEMO_CLASS_MAP.get(cls_name, cls_name)
                color = OBJECT_COLORS.get(quest_class, OBJECT_COLORS["default"])

                results.append({
                    "detected_class": quest_class,
                    "coco_class": cls_name,
                    "label": _label(quest_class),
                    "confidence": round(conf, 2),
                    "bbox": normalize_bbox(bx, by, bw, bh, w, h),
                    "color": color,
                    "type": "object",
                })

    except Exception as e:
        log.warning("YOLOv8 ошибка: %s", e)

    return results


def _label(quest_class: str) -> str:
    labels = {
        "fire_extinguisher": "Огнетушитель",
        "person":            "Человек",
        "workstation":       "Рабочее место",
        "control_panel":     "Панель управления",
        "cutting_tool":      "Режущий инструмент",
        "handheld_device":   "Устройство",
    }
    return labels.get(quest_class, quest_class)
