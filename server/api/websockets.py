import logging
from fastapi import WebSocket
import json

logger = logging.getLogger("messenger.websockets")

class ConnectionManager:
    def __init__(self):
        # Словарь: { "username": set(websocket1, websocket2) } (поддержка нескольких устройств)
        self.active_connections: dict[str, set[WebSocket]] = {}

    def is_online(self, username: str) -> bool:
        return username in self.active_connections and len(self.active_connections[username]) > 0

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        if username not in self.active_connections:
            self.active_connections[username] = set()
        self.active_connections[username].add(websocket)
        logger.info(f"[Онлайн] {username} подключился.")

    def disconnect(self, websocket: WebSocket, username: str):
        if username in self.active_connections:
            self.active_connections[username].discard(websocket)
            if not self.active_connections[username]:
                del self.active_connections[username]
        logger.info(f"[Оффлайн] {username} отключился.")

    async def send_to_user(self, username: str, message: dict):
        """Отправляет JSON-сообщение всем активным сессиям пользователя"""
        if username in self.active_connections:
            # Превращаем dict в строку JSON, как это было в старом сервере
            text_data = json.dumps(message)
            for connection in list(self.active_connections[username]):
                try:
                    await connection.send_text(text_data)
                except Exception:
                    self.disconnect(connection, username)

    async def disconnect_other_sessions(self, username: str, current_token_id: str):
        """Закрывает и отключает все WebSocket сессии пользователя, кроме текущей"""
        if username in self.active_connections:
            connections = list(self.active_connections[username])
            for ws in connections:
                if getattr(ws, "token_id", None) != current_token_id:
                    try:
                        await ws.close(code=4000)
                    except Exception:
                        pass
                    self.disconnect(ws, username)

    async def broadcast(self, message: dict):
        """Отправляет сообщение абсолютно всем, кто сейчас онлайн"""
        text_data = json.dumps(message)
        for username, connections in list(self.active_connections.items()):
            for connection in list(connections):
                try:
                    await connection.send_text(text_data)
                except Exception:
                    pass

manager = ConnectionManager()