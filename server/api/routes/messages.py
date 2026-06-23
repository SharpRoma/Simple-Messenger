import os
import uuid
import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.config import settings
from api.dependencies import get_current_user
from api.websockets import manager
from models.message import Message
from models.chat import ChatMember
from models.user import User
from schemas.message import HistoryResponse

router = APIRouter(prefix="/messages", tags=["Сообщения и Файлы"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/{chat_id}", response_model=HistoryResponse)
async def get_history(chat_id: int, limit: int = 50, offset: int = 0, username: str = Depends(get_current_user),
                      db: AsyncSession = Depends(get_db)):
    """Получить историю сообщений чата"""
    # Проверяем права (состоит ли юзер в чате)
    member_check = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.username == username))
    if not member_check.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Вы не состоите в этом чате")

    # Помечаем сообщения от других пользователей как прочитанные
    stmt = select(Message).where(
        Message.chat_id == chat_id,
        Message.sender != username,
        Message.is_read == False
    )
    unread_result = await db.execute(stmt)
    unread_messages = unread_result.scalars().all()
    if unread_messages:
        for m in unread_messages:
            m.is_read = True
        await db.commit()
        # Рассылаем всем участникам чата оповещение о прочтении
        members = (await db.execute(select(ChatMember.username).where(ChatMember.chat_id == chat_id))).scalars().all()
        for member in members:
            await manager.send_to_user(member, {"action": "messages_read", "chat_id": chat_id})

    # Грузим сообщения
    query = select(Message).where(Message.chat_id == chat_id).order_by(Message.timestamp.desc()).limit(limit).offset(
        offset)
    result = await db.execute(query)
    messages = result.scalars().all()

    # Разворачиваем, чтобы старые были сверху
    msg_list = [
        {
            "id": m.id,
            "sender": m.sender,
            "text": m.text,
            "file_name": m.file_name,
            "timestamp": m.timestamp,
            "updated_at": m.updated_at,
            "is_read": m.is_read
        }
        for m in reversed(messages)
    ]
    return {"chat_id": chat_id, "messages": msg_list}


@router.post("/{chat_id}/files")
async def upload_file(
        chat_id: int,
        file: UploadFile = File(...),
        username: str = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Отправка файла чанками"""
    member_check = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.username == username))
    if not member_check.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    # МАГИЯ: Сохраняем файл на диск кусочками по 1 МБ
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    # Сохраняем в БД
    new_msg = Message(chat_id=chat_id, sender=username, file_name=file.filename, file_path=file_path,
                      timestamp=int(time.time()))
    db.add(new_msg)
    await db.commit()
    await db.refresh(new_msg)

    # Рассылаем уведомление в сокеты
    msg_obj = {"id": new_msg.id, "sender": new_msg.sender, "text": "", "file_name": new_msg.file_name,
               "timestamp": new_msg.timestamp, "updated_at": None, "is_read": False}
    members = (await db.execute(select(ChatMember.username).where(ChatMember.chat_id == chat_id))).scalars().all()

    for member in members:
        await manager.send_to_user(member, {"action": "new_msg", "chat_id": chat_id, "message": msg_obj})

    return {"status": "ok", "msg_id": new_msg.id}


@router.get("/files/{msg_id}")
async def download_file(msg_id: int, username: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Скачать файл по ID сообщения"""
    query = select(Message, ChatMember).join(ChatMember, Message.chat_id == ChatMember.chat_id).where(
        Message.id == msg_id, ChatMember.username == username)
    result = await db.execute(query)
    row = result.first()

    if not row or not row.Message.file_path or not os.path.exists(row.Message.file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")

    # FastAPI сам отдаст файл бинарным потоком
    return FileResponse(path=row.Message.file_path, filename=row.Message.file_name)


@router.delete("/{msg_id}")
async def delete_message(msg_id: int, username: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    msg = (await db.execute(select(Message).where(Message.id == msg_id))).scalar_one_or_none()

    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")

    # Удалить может только автор
    if msg.sender != username:
        raise HTTPException(status_code=403, detail="Это не ваше сообщение")

    chat_id = msg.chat_id

    await db.delete(msg)
    await db.commit()

    # Уведомляем всех в чате через сокет
    members = (await db.execute(select(ChatMember.username).where(ChatMember.chat_id == chat_id))).scalars().all()
    for member in members:
        await manager.send_to_user(member, {"action": "msg_deleted", "chat_id": chat_id, "msg_id": msg_id})

    return {"status": "ok"}


@router.put("/{msg_id}")
async def edit_message(
    msg_id: int,
    text: str = Form(None),
    delete_file: bool = Form(False),
    file: UploadFile = File(None),
    username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Редактирование сообщения и его файлов"""
    msg = (await db.execute(select(Message).where(Message.id == msg_id))).scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
 
    # Редактировать может только автор
    if msg.sender != username:
        raise HTTPException(status_code=403, detail="Вы не можете редактировать чужие сообщения")
 
    # 1. Удаление файла или его замена
    if delete_file or file:
        msg.file_name = None
        msg.file_path = None
        # (SQLAlchemy event listener сам удалит файл с диска при коммите, 
        # так как мы очищаем file_path или удаляем запись)
 
    # 2. Если загружается новый файл
    if file:
        ext = os.path.splitext(file.filename)[1]
        unique_name = f"{uuid.uuid4()}{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
 
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
 
        msg.file_name = file.filename
        msg.file_path = file_path
 
    # 3. Обновляем текст
    if text is not None:
        msg.text = text
 
    # 4. Проверяем, не пустое ли сообщение
    if not msg.text and not msg.file_name:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
 
    # Записываем время изменения
    msg.updated_at = int(time.time())
    await db.commit()
    await db.refresh(msg)
 
    # Рассылаем уведомление о редактировании всем участникам
    msg_obj = {
        "id": msg.id,
        "sender": msg.sender,
        "text": msg.text,
        "file_name": msg.file_name,
        "timestamp": msg.timestamp,
        "updated_at": msg.updated_at,
        "is_read": msg.is_read
    }
 
    members = (await db.execute(select(ChatMember.username).where(ChatMember.chat_id == msg.chat_id))).scalars().all()
    for member in members:
        await manager.send_to_user(member, {
            "action": "msg_edited",
            "chat_id": msg.chat_id,
            "message": msg_obj
        })
 
    return {"status": "ok", "message": msg_obj}


@router.get("/{chat_id}/search")
async def search_messages(
    chat_id: int,
    query: str = "",
    username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Поиск сообщений по тексту и имени файла в рамках чата (только для членов чата)"""
    # Проверяем, состоит ли пользователь в чате
    member_check = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.username == username)
    )
    if not member_check.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Вы не состоите в этом чате")

    if not query.strip():
        return {"messages": []}

    # Ищем сообщения с фильтром по тексту или имени файла
    stmt = select(Message).where(
        Message.chat_id == chat_id,
        (Message.text.like(f"%{query}%") | Message.file_name.like(f"%{query}%"))
    ).order_by(Message.timestamp.desc()).limit(100)

    result = await db.execute(stmt)
    messages = result.scalars().all()

    # Форматируем ответ
    msg_list = [{
        "id": m.id,
        "sender": m.sender,
        "text": m.text,
        "file_name": m.file_name,
        "timestamp": m.timestamp,
        "updated_at": m.updated_at
    } for m in messages]
    
    return {"messages": msg_list}