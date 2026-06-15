from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from api.dependencies import get_username_from_token
from api.websockets import manager
from models.message import Message
from models.chat import ChatMember
from models.user import User

import json

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str, db: AsyncSession = Depends(get_db)):
    # 1. Проверяем токен при подключении
    try:
        username = get_username_from_token(token)
    except Exception as e:
        await websocket.close(code=1008)  # 1008 - Ошибка авторизации
        return

    # --- ДОБАВЛЕНО: Узнаем, админ ли это ---
    user_obj = await db.execute(select(User).where(User.username == username))
    user = user_obj.scalar_one_or_none()
    is_admin = user.is_admin if user else False

    # 2. Регистрируем пользователя как "Онлайн"
    await manager.connect(websocket, username)

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
                        continue  # Игнорируем

                # Сохраняем сообщение в БД (Асинхронно)
                import time
                new_msg = Message(
                    chat_id=chat_id,
                    sender=username,
                    text=text,
                    timestamp=int(time.time())
                )
                db.add(new_msg)
                await db.commit()
                await db.refresh(new_msg)  # Получаем ID из базы

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

            # ... (остальные экшены типа delete_msg, req_file добавим чуть позже)

    except WebSocketDisconnect:
        manager.disconnect(websocket, username)
    except Exception as e:
        print(f"Ошибка сокета у {username}: {e}")
        manager.disconnect(websocket, username)