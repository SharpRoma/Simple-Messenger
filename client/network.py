import httpx
import websockets
import json
import traceback
import ssl


class MessengerNetwork:
    def __init__(self, on_message_received, on_disconnected):
        self.on_message_received = on_message_received
        self.on_disconnected = on_disconnected

        self.token = None
        self.host = None
        self.port = None
        self.api_url = ""
        self.ws_url = ""
        self.ws = None

        # Разрешаем клиенту доверять самоподписанным 10-летним сертификатам сервера
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    async def connect(self, host, port, username, password, mode="login", secret=""):
        self.host = host
        self.port = port
        # ВНИМАНИЕ: Теперь мы используем HTTPS и WSS!
        self.api_url = f"https://{host}:{port}/api"
        self.ws_url = f"wss://{host}:{port}/ws"

        # Отключаем проверку сертификата в httpx (verify=False)
        async with httpx.AsyncClient(verify=False) as client:
            try:
                if mode == "register":
                    res = await client.post(f"{self.api_url}/auth/register", json={
                        "username": username, "password": password, "secret": secret
                    })
                else:
                    res = await client.post(f"{self.api_url}/auth/login", json={
                        "username": username, "password": password
                    })

                if res.status_code != 200:
                    return {"status": "error", "msg": res.json().get("detail", "Ошибка авторизации")}

                self.token = res.json().get("access_token")
                return {"status": "ok"}
            except Exception as e:
                print(f"Connection Error: {e}")
                return {"status": "error", "msg": "Сервер недоступен"}

    async def send(self, data: dict):
        action = data.get("action")
        headers = {"Authorization": f"Bearer {self.token}"}

        if action == "send_msg" and self.ws:
            await self.ws.send(json.dumps(data))
            return

        async with httpx.AsyncClient(verify=False) as client:
            try:
                if action == "get_chats":
                    res = await client.get(f"{self.api_url}/chats/", headers=headers)
                    if res.status_code == 200:
                        await self.on_message_received({"action": "chat_list", "chats": res.json().get("chats")})

                elif action == "get_history":
                    chat_id = data.get("chat_id")
                    res = await client.get(f"{self.api_url}/messages/{chat_id}?limit={data.get('limit', 50)}",
                                           headers=headers)
                    if res.status_code == 200:
                        await self.on_message_received({"action": "history", **res.json()})

                elif action == "create_dialog":
                    res = await client.post(f"{self.api_url}/chats/dialog",
                                            json={"target_username": data.get("target")}, headers=headers)
                    if res.status_code == 200:
                        await self.on_message_received({"action": "dialog_created", **res.json()})

                elif action == "delete_msg":
                    await client.delete(f"{self.api_url}/messages/{data.get('msg_id')}", headers=headers)

                elif action == "send_file":
                    with open(data.get("filepath"), "rb") as f:
                        files = {"file": (data.get("filename"), f)}
                        await client.post(f"{self.api_url}/messages/{data.get('chat_id')}/files", files=files,
                                          headers=headers)

                elif action == "req_file":
                    save_path = data.get("save_path")
                    async with client.stream("GET", f"{self.api_url}/messages/files/{data.get('msg_id')}",
                                             headers=headers) as res:
                        if res.status_code == 200:
                            with open(save_path, "wb") as f:
                                async for chunk in res.aiter_bytes():
                                    f.write(chunk)
                            await self.on_message_received({"action": "file_saved", "filepath": save_path})

            except Exception as e:
                print(f"Network REST Error ({action}): {e}")

    async def listen(self):
        try:
            # ВНИМАНИЕ: Передаем наш ssl_context для WSS-соединения!
            async with websockets.connect(f"{self.ws_url}?token={self.token}", ssl=self.ssl_context) as ws:
                self.ws = ws
                while True:
                    message = await ws.recv()
                    await self.on_message_received(json.loads(message))
        except Exception as e:
            print("\n--- ОБРЫВ СВЯЗИ (WebSocket) ---")
            traceback.print_exc()
            await self.on_disconnected()

    async def disconnect(self):
        if self.ws:
            await self.ws.close()
            self.ws = None