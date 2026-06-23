import json
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from api.dependencies import get_username_from_token
from api.websockets import manager
from core.database import async_session_maker
from core import crud
from models.message import Message


router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    # 1. Проверяем токен при подключении
    try:
        username = get_username_from_token(token)
    except Exception as e:
        await websocket.close(code=1008)  # 1008 - Ошибка авторизации
        return

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

                async with async_session_maker() as db:
                    # Проверяем, состоит ли юзер в чате
                    if not await crud.is_user_in_chat(db, chat_id, username):
                        continue

                    # Сохраняем сообщение в БД
                    new_msg = await crud.create_message(db, chat_id, username, text)

                    msg_obj = {
                        "id": new_msg.id,
                        "sender": new_msg.sender,
                        "text": new_msg.text,
                        "file_name": None,
                        "timestamp": new_msg.timestamp,
                        "updated_at": None,
                        "is_read": False
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

            elif action == "read_chat":
                chat_id = data.get("chat_id")
                async with async_session_maker() as db:
                    if await crud.is_user_in_chat(db, chat_id, username):
                        stmt = select(Message).where(
                            Message.chat_id == chat_id,
                            Message.sender != username,
                            Message.is_read == False
                        )
                        result = await db.execute(stmt)
                        unread = result.scalars().all()
                        if unread:
                            for m in unread:
                                m.is_read = True
                            await db.commit()
                            
                            members = await crud.get_chat_member_usernames(db, chat_id)
                            for member in members:
                                await manager.send_to_user(member, {"action": "messages_read", "chat_id": chat_id})

            elif action == "typing":
                chat_id = data.get("chat_id")

                async with async_session_maker() as db:
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