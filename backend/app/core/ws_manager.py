"""
WebSocket Connection Manager.

Управляет активными WS-соединениями пользователей.
Каждый пользователь может иметь одно активное соединение.
"""

import logging
from fastapi import WebSocket

log = logging.getLogger("casper.ws")


class WSManager:
    def __init__(self):
        # user_id → WebSocket
        self._connections: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        # Закрываем старое соединение если есть
        if user_id in self._connections:
            try:
                await self._connections[user_id].close()
            except Exception:
                pass
        self._connections[user_id] = websocket
        log.info("WS: пользователь %d подключился (всего: %d)", user_id, len(self._connections))

    def disconnect(self, user_id: int):
        self._connections.pop(user_id, None)
        log.info("WS: пользователь %d отключился (всего: %d)", user_id, len(self._connections))

    async def send(self, user_id: int, data: dict):
        ws = self._connections.get(user_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception as e:
                log.warning("WS send error user=%d: %s", user_id, e)
                self.disconnect(user_id)

    @property
    def active_count(self) -> int:
        return len(self._connections)


# Синглтон — один менеджер на всё приложение
ws_manager = WSManager()
