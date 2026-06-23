import json
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from api.dependencies import get_username_from_token
from api.websockets import manager
from models.message import Message
from models.chat import ChatMember
from models.user import User
from core.database import async_session_maker


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
    user_obj = await db.execute(select(User).where(User.username == username))
    user = user_obj.scalar_one_or_none()
    is_admin = user.is_admin if user else False

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
                member_check = await db.execute(
                    select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.username == username)
                )
                # --- Пропускаем проверку, если это админ ---
                if not is_admin:
                    member_check = await db.execute(
                        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.username == username)
                    )
                    if not member_check.scalar_one_or_none():
                        continue

                # Сохраняем сообщение в БД
                new_msg = Message(
                    chat_id=chat_id,
                    sender=username,
                    text=text,
                    timestamp=int(time.time())
                )
                db.add(new_msg)
                await db.commit()
                await db.refresh(new_msg)

                msg_obj = {
                    "id": new_msg.id,
                    "sender": new_msg.sender,
                    "text": new_msg.text,
                    "file_name": None,
                    "timestamp": new_msg.timestamp
                }

                # Находим всех участников чата
                members_result = await db.execute(select(ChatMember.username).where(ChatMember.chat_id == chat_id))
                members = members_result.scalars().all()

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
                    member_check = await db.execute(
                        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.username == username)
                    )
                    if not member_check.scalar_one_or_none():
                        continue

                # Находим всех участников
                members = (
                    await db.execute(select(ChatMember.username).where(ChatMember.chat_id == chat_id))).scalars().all()

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
            db_user = await session.get(User, username)
            if db_user:
                db_user.last_seen = current_time
                await session.commit()

        # 2. Сообщаем всем, что юзер вышел (и передаем время выхода)
        # Рассылаем статус offline только если юзер закрыл ВСЕ свои вкладки/устройства
        if not manager.is_online(username):
            await manager.broadcast({
                "action": "status",
                "username": username,
                "status": "offline",
                "last_seen": current_time
            })