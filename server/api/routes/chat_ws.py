import json
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from api.dependencies import get_username_from_token
from api.websockets import manager
from core.database import async_session_maker
from core import crud


router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str, db: AsyncSession = Depends(get_db)):
    # 1. Проверяем токен при подключении
    try:
        username = get_username_from_token(token)
    except Exception as e:
        await websocket.close(code=1008)  # 1008 - Ошибка авторизации
        return

    # --- Узнаем, админ ли это ---
    is_admin = await crud.is_user_admin(db, username)

    # 2. Регистрируем пользователя как "Онлайн"
    await manager.connect(websocket, username)

    await manager.broadcast({"action": "status", "username": username, "status": "online"})

    try:
        # 3. Бесконечный цикл прослушивания сообщений
        while True:
            # Ждем сообщение от клиента
            data_str = await websocket.receive_text()
            data = json.loads(data_str)

            action = data.get("action")

            if action == "send_msg":
                chat_id = data.get("chat_id")
                text = data.get("text")

                # Проверяем, состоит ли юзер в чате
                if not is_admin:
                    if not await crud.is_user_in_chat(db, chat_id, username):
                        continue

                # Сохраняем сообщение в БД
                new_msg = await crud.create_message(db, chat_id, username, text)

                msg_obj = {
                    "id": new_msg.id,
                    "sender": new_msg.sender,
                    "text": new_msg.text,
                    "file_name": None,
                    "timestamp": new_msg.timestamp
                }

                # Находим всех участников чата
                members = await crud.get_chat_member_usernames(db, chat_id)

                # Рассылаем всем участникам
                for member in members:
                    await manager.send_to_user(member, {
                        "action": "new_msg",
                        "chat_id": chat_id,
                        "message": msg_obj
                    })

            elif action == "typing":
                chat_id = data.get("chat_id")

                if not is_admin:
                    if not await crud.is_user_in_chat(db, chat_id, username):
                        continue

                # Находим всех участников
                members = await crud.get_chat_member_usernames(db, chat_id)

                # Рассылаем всем, кроме самого отправителя
                for member in members:
                    if member != username:
                        await manager.send_to_user(member, {
                            "action": "typing",
                            "chat_id": chat_id,
                            "username": username
                        })

    except (WebSocketDisconnect, Exception) as e:
        # Если юзер отключился
        manager.disconnect(websocket, username)
        # 1. Записываем время выхода в базу данных
        current_time = int(time.time())
        async with async_session_maker() as session:
            await crud.update_user_last_seen(session, username, current_time)

        # 2. Сообщаем всем, что юзер вышел (и передаем время выхода)
        # Рассылаем статус offline только если юзер закрыл ВСЕ свои вкладки/устройства
        if not manager.is_online(username):
            await manager.broadcast({
                "action": "status",
                "username": username,
                "status": "offline",
                "last_seen": current_time
            })