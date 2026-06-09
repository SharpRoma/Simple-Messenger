import asyncio
import json


class MessengerNetwork:
    def __init__(self, on_message_received, on_disconnected):
        self.reader = None
        self.writer = None
        self.on_message_received = on_message_received
        self.on_disconnected = on_disconnected

    async def connect(self, host, port, username, password):
        """Устанавливает соединение и проходит авторизацию"""
        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)
            auth_data = {"username": username, "password": password}
            await self.send(auth_data)

            response_line = await self.reader.readline()
            if not response_line:
                return {"status": "error", "msg": "Сервер разорвал соединение при авторизации"}

            return json.loads(response_line.decode().strip())
        except Exception as e:
            return {"status": "error", "msg": str(e)}

    async def send(self, data: dict):
        """Отправляет JSON словарь на сервер"""
        if self.writer:
            self.writer.write(json.dumps(data).encode() + b'\n')
            await self.writer.drain()

    async def listen(self):
        """Бесконечный цикл прослушивания входящих сообщений"""
        try:
            while True:
                line = await self.reader.readline()
                if not line:
                    await self.on_disconnected()
                    break

                data = json.loads(line.decode().strip())
                await self.on_message_received(data)
        except Exception:
            await self.on_disconnected()

    async def disconnect(self):
        """Закрывает сокет"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()