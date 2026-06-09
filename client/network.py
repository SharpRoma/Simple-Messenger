import asyncio
import json

class MessengerNetwork:
    def __init__(self, on_message_received, on_disconnected):
        self.reader = None
        self.writer = None
        self.on_message_received = on_message_received
        self.on_disconnected = on_disconnected

    # --- ДОБАВЛЕН mode и secret ---
    async def connect(self, host, port, username, password, mode="login", secret=""):
        try:
            # Увеличили лимит под файлы в будущем
            self.reader, self.writer = await asyncio.open_connection(host, port, limit=1024*1024*50)
            auth_data = {"mode": mode, "username": username, "password": password, "secret": secret}
            await self.send(auth_data)

            response_line = await self.reader.readline()
            if not response_line:
                return {"status": "error", "msg": "Сервер разорвал соединение"}
            return json.loads(response_line.decode().strip())
        except Exception as e:
            return {"status": "error", "msg": str(e)}

    async def send(self, data: dict):
        if self.writer:
            self.writer.write(json.dumps(data).encode() + b'\n')
            await self.writer.drain()

    async def listen(self):
        try:
            while True:
                line = await self.reader.readline()
                if not line:
                    await self.on_disconnected()
                    break
                await self.on_message_received(json.loads(line.decode().strip()))
        except Exception:
            await self.on_disconnected()

    async def disconnect(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()