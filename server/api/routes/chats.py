from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_db
from api.dependencies import get_username_from_token
from models.chat import Chat, ChatMember
from models.user import User
from schemas.chat import ChatListResponse, ChatResponse, CreateDialogRequest

from api.dependencies import get_current_user

# Создаем роутер
router = APIRouter(prefix="/chats", tags=["Чаты"])


@router.get("/", response_model=ChatListResponse)
async def get_my_chats(username: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Возвращает список всех чатов пользователя"""
    query = select(Chat).join(ChatMember).where(ChatMember.username == username)
    result = await db.execute(query)
    chats = result.scalars().all()

    return {"chats": [{"id": c.id, "name": c.name, "type": c.type} for c in chats]}


@router.post("/dialog")
async def create_dialog(req: CreateDialogRequest, username: str = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """Создает личный диалог с другим пользователем"""
    target = req.target_username

    # 1. Проверяем, существует ли целевой юзер
    user_check = await db.execute(select(User).where(User.username == target))
    if not user_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # 2. Ищем уже существующий диалог
    my_chats_query = select(ChatMember.chat_id).where(ChatMember.username == username)
    my_chats = (await db.execute(my_chats_query)).scalars().all()

    target_chats_query = select(ChatMember.chat_id).where(ChatMember.username == target)
    target_chats = (await db.execute(target_chats_query)).scalars().all()

    common_chats = set(my_chats).intersection(set(target_chats))

    if common_chats:
        # Проверяем, есть ли среди общих чатов именно 'dialog'
        dialog_query = select(Chat).where(Chat.id.in_(common_chats), Chat.type == 'dialog')
        existing_dialog = (await db.execute(dialog_query)).scalar_one_or_none()
        if existing_dialog:
            return {"chat_id": existing_dialog.id, "target": target}

    # 3. Создаем новый диалог
    new_chat = Chat(name=f"{username}_{target}", type="dialog")
    db.add(new_chat)
    await db.flush()

    db.add(ChatMember(chat_id=new_chat.id, username=username))
    db.add(ChatMember(chat_id=new_chat.id, username=target))
    await db.commit()

    return {"chat_id": new_chat.id, "target": target}