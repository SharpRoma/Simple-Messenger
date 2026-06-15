from fastapi import WebSocket
import json

class ConnectionManager:
    def __init__(self):
        # Словарь: { "username": set(websocket1, websocket2) } (поддержка нескольких устройств)
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        if username not in self.active_connections:
            self.active_connections[username] = set()
        self.active_connections[username].add(websocket)
        print(f"[Онлайн] {username} подключился.")

    def disconnect(self, websocket: WebSocket, username: str):
        if username in self.active_connections:
            self.active_connections[username].discard(websocket)
            if not self.active_connections[username]:
                del self.active_connections[username]
        print(f"[Оффлайн] {username} отключился.")

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

manager = ConnectionManager()