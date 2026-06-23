import httpx
import websockets
import json
import traceback
import ssl
import logging

logger = logging.getLogger("messenger.network")


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

        if host in ["127.0.0.1", "localhost"]:
            self.api_url = f"http://{host}:{port}/api"
            self.ws_url = f"ws://{host}:{port}/ws"
        else:
            self.api_url = f"https://{host}:{port}/api"
            self.ws_url = f"wss://{host}:{port}/ws"

        # Отключаем проверку сертификата в httpx (verify=False)
        async with httpx.AsyncClient(verify=False) as client:
            try:
                if mode == "reset":
                    res = await client.post(f"{self.api_url}/auth/reset-password", json={
                        "username": username, "new_password": password, "secret": secret
                    })
                    if res.status_code != 200:
                        return {"status": "error", "msg": res.json().get("detail", "Ошибка сброса")}
                    return {"status": "ok"}

                elif mode == "register":
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
                logger.error(f"Connection Error: {e}")
                return {"status": "error", "msg": "Сервер недоступен"}

    async def search_users(self, query: str) -> list:
        if not self.token:
            return []
        headers = {"Authorization": f"Bearer {self.token}"}
        async with httpx.AsyncClient(verify=False) as client:
            try:
                res = await client.get(f"{self.api_url}/users/search?query={query}", headers=headers)
                if res.status_code == 200:
                    return res.json().get("users", [])
            except Exception as e:
                logger.error(f"Search users error: {e}")
        return []

    async def send(self, data: dict):
        action = data.get("action")
        headers = {"Authorization": f"Bearer {self.token}"}

        if action in ["send_msg", "typing"] and self.ws:
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
                    limit = data.get("limit", 20)
                    offset = data.get("offset", 0)  # <--- Получаем сдвиг от интерфейса
                    res = await client.get(f"{self.api_url}/messages/{chat_id}?limit={limit}&offset={offset}",
                                           headers=headers)
                    if res.status_code == 200:
                        await self.on_message_received({"action": "history", "offset": offset, **res.json()})

                elif action == "search_messages":
                    chat_id = data.get("chat_id")
                    query = data.get("query")
                    res = await client.get(f"{self.api_url}/messages/{chat_id}/search?query={query}", headers=headers)
                    if res.status_code == 200:
                        await self.on_message_received({
                            "action": "search_results",
                            "chat_id": chat_id,
                            "messages": res.json().get("messages", [])
                        })

                elif action == "create_dialog":
                    res = await client.post(f"{self.api_url}/chats/dialog",
                                            json={"target_username": data.get("target")}, headers=headers)
                    if res.status_code == 200:
                        await self.on_message_received({"action": "dialog_created", **res.json()})

                elif action == "delete_msg":
                    await client.delete(f"{self.api_url}/messages/{data.get('msg_id')}", headers=headers)

                elif action == "edit_msg":
                    msg_id = data.get("msg_id")
                    text = data.get("text")
                    delete_file = data.get("delete_file", False)
                    new_filepath = data.get("new_filepath")
                    new_filename = data.get("new_filename")

                    form_data = {
                        "text": text if text is not None else "",
                        "delete_file": "true" if delete_file else "false"
                    }

                    files = None
                    f = None
                    if new_filepath:
                        f = open(new_filepath, "rb")
                        files = {"file": (new_filename, f)}

                    try:
                        res = await client.put(
                            f"{self.api_url}/messages/{msg_id}",
                            data=form_data,
                            files=files,
                            headers=headers
                        )
                        if res.status_code != 200:
                            logger.error(f"Error editing message REST status: {res.status_code}")
                    finally:
                        if f:
                            f.close()

                elif action == "get_chat_members":
                    res = await client.get(f"{self.api_url}/chats/{data.get('chat_id')}/members", headers=headers)
                    if res.status_code == 200:
                        await self.on_message_received({"action": "chat_members_data", **res.json()})

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

                elif action == "create_group":
                    res = await client.post(f"{self.api_url}/chats/group", json={"name": data.get("name")},
                                            headers=headers)
                    if res.status_code == 200:
                        await self.on_message_received({"action": "group_created", **res.json()})

                elif action == "add_member":
                    res = await client.post(f"{self.api_url}/chats/{data.get('chat_id')}/members",
                                            json={"username": data.get("username")}, headers=headers)
                    if res.status_code == 200:
                        await self.on_message_received({"action": "member_added"})

            except Exception as e:
                logger.error(f"Network REST Error ({action}): {e}")
                if action == "get_history":
                    await self.on_message_received({
                        "action": "history_error",
                        "chat_id": data.get("chat_id"),
                        "offset": data.get("offset", 0)
                    })

    async def listen(self):
        """Бесконечное прослушивание входящих сообщений по WebSocket"""
        try:
            # --- ИСПРАВЛЕНО: Умная подстановка SSL ---
            ssl_ctx = self.ssl_context if self.ws_url.startswith("wss://") else None

            async with websockets.connect(f"{self.ws_url}?token={self.token}", ssl=ssl_ctx) as ws:
                self.ws = ws
                while True:
                    message = await ws.recv()
                    await self.on_message_received(json.loads(message))
        except Exception as e:
            logger.error("ОБРЫВ СВЯЗИ (WebSocket)", exc_info=True)
            await self.on_disconnected()

    async def disconnect(self):
        if self.ws:
            await self.ws.close()
            self.ws = None