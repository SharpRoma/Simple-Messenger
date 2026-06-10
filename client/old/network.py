import asyncio
import json
import ssl  # <--- БИБЛИОТЕКА ДЛЯ ШИФРОВАНИЯ


class MessengerNetwork:
    def __init__(self, on_message_received, on_disconnected):
        self.reader = None
        self.writer = None
        self.on_message_received = on_message_received
        self.on_disconnected = on_disconnected

    async def connect(self, host, port, username, password, mode="login", secret=""):
        try:
            # --- НАСТРОЙКА SSL ДЛЯ КЛИЕНТА ---
            ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            # Отключаем строгую проверку домена (т.к. у нас самоподписанный сертификат по IP)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # Передаем ssl=ssl_context при подключении
            self.reader, self.writer = await asyncio.open_connection(
                host, port,
                ssl=ssl_context,
                limit=1024 * 1024 * 50
            )

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