from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_db
from api.dependencies import get_username_from_token
from models.chat import Chat, ChatMember
from models.user import User
from schemas.chat import ChatListResponse, ChatResponse, CreateDialogRequest, CreateGroupRequest, AddMemberRequest

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


@router.post("/group")
async def create_group(req: CreateGroupRequest, username: str = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    """Создает групповой чат"""
    new_chat = Chat(name=req.name, type="group")
    db.add(new_chat)
    await db.flush()

    db.add(ChatMember(chat_id=new_chat.id, username=username))
    await db.commit()
    return {"chat_id": new_chat.id, "name": new_chat.name}


@router.post("/{chat_id}/members")
async def add_member(chat_id: int, req: AddMemberRequest, username: str = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
    """Добавляет пользователя в групповой чат"""
    # Проверяем, состоит ли текущий юзер в чате (или он админ)
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    is_admin = user.is_admin if user else False

    if not is_admin:
        member_check = await db.execute(
            select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.username == username))
        if not member_check.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не состоите в этом чате")

    # Проверяем, что это именно группа
    chat = (await db.execute(select(Chat).where(Chat.id == chat_id))).scalar_one_or_none()
    if not chat or chat.type != "group":
        raise HTTPException(status_code=400, detail="Добавлять участников можно только в группы")

    # Проверяем, существует ли целевой юзер
    target_user = (await db.execute(select(User).where(User.username == req.username))).scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    try:
        db.add(ChatMember(chat_id=chat_id, username=req.username))
        await db.commit()

        # Сигнализируем добавленному пользователю через WebSocket, чтобы у него обновился список чатов
        from api.websockets import manager
        await manager.send_to_user(req.username, {"action": "chat_added"})

    except Exception:
        pass  # Если юзер уже в чате (IntegrityError), просто игнорируем

    return {"status": "ok"}


@router.get("/{chat_id}/members")
async def get_chat_members(chat_id: int, username: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Возвращает профиль чата: список участников и их статусы"""
    # 1. Проверка прав (админ или участник)
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    is_admin = user.is_admin if user else False

    if not is_admin:
        member_check = await db.execute(
            select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.username == username))
        if not member_check.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не состоите в этом чате")

    # 2. Достаем всех участников и их last_seen из базы
    query = (
        select(User.username, User.last_seen)
        .join(ChatMember, ChatMember.username == User.username)
        .where(ChatMember.chat_id == chat_id)
    )
    result = await db.execute(query)

    # 3. Формируем красивый список для интерфейса
    from api.websockets import manager
    members_list = []

    for row in result:
        member_name, last_seen = row.username, row.last_seen
        is_online = manager.is_online(member_name)

        members_list.append({
            "username": member_name,
            "is_online": is_online,
            "last_seen": last_seen
        })

    return {"members": members_list}