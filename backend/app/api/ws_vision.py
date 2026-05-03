"""
WebSocket Vision эндпоинт.

Протокол (JSON сообщения):

Клиент → Сервер:
  { "type": "frame", "image": "<base64>", "run_ppe": false, "run_objects": true }
  { "type": "ping" }

Сервер → Клиент:
  {
    "type": "detections",
    "markers":        [...],
    "objects":        [...],
    "ppe":            {...},
    "all_detections": [...],
    "processing_ms":  45,
    "quest_events":   [...]   ← новое: квесты завершённые в этом кадре
  }
  { "type": "pong" }
  { "type": "error", "message": "..." }
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.ws_manager import ws_manager
from app.cv.pipeline import process_frame
from app.db.database import SessionLocal
from app.db.models import User
from app.game.quest_trigger import process_cv_detections

log = logging.getLogger("casper.ws.vision")
settings = get_settings()
router = APIRouter()


def _get_user_from_token(token: str) -> User | None:
    """Валидировать JWT и вернуть пользователя из БД."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = int(payload.get("sub", 0))
    except (JWTError, ValueError):
        return None

    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


@router.websocket("/vision")
async def vision_websocket(websocket: WebSocket, token: str = ""):
    """
    WebSocket для стрима кадров с камеры.

    Подключение: ws://localhost:8000/ws/vision?token=<JWT>

    Клиент отправляет кадры, сервер возвращает детекции + квест-события.
    """
    user = _get_user_from_token(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await ws_manager.connect(websocket, user.id)

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "frame":
                b64 = msg.get("image", "")
                if not b64:
                    await websocket.send_json({"type": "error", "message": "Нет изображения"})
                    continue

                result = process_frame(
                    b64_image=b64,
                    run_ppe=msg.get("run_ppe", False),
                    run_objects=msg.get("run_objects", True),
                )

                # Проверяем детекции против активных квестов
                # Открываем отдельную сессию — WS живёт дольше одного запроса
                quest_events: list[dict] = []
                db = SessionLocal()
                try:
                    # Перечитываем user чтобы сессия была актуальной
                    fresh_user = db.query(User).filter(User.id == user.id).first()
                    if fresh_user:
                        quest_events = process_cv_detections(
                            db=db,
                            user=fresh_user,
                            objects=result["objects"],
                            markers=result["markers"],
                        )
                        # Обновляем локальный объект для следующих кадров
                        user.total_xp = fresh_user.total_xp
                        user.level = fresh_user.level
                finally:
                    db.close()

                await websocket.send_json({
                    "type":           "detections",
                    "markers":        result["markers"],
                    "objects":        result["objects"],
                    "ppe":            result["ppe"],
                    "all_detections": result["all_detections"],
                    "processing_ms":  result["processing_ms"],
                    "quest_events":   quest_events,
                })

    except WebSocketDisconnect:
        log.info("WS: пользователь %s отключился", user.username)
    except Exception as e:
        log.error("WS ошибка для %s: %s", user.username, e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        ws_manager.disconnect(user.id)
