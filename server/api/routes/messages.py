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

    # Грузим сообщения
    query = select(Message).where(Message.chat_id == chat_id).order_by(Message.timestamp.desc()).limit(limit).offset(
        offset)
    result = await db.execute(query)
    messages = result.scalars().all()

    # Разворачиваем, чтобы старые были сверху
    msg_list = [{"id": m.id, "sender": m.sender, "text": m.text, "file_name": m.file_name, "timestamp": m.timestamp} for
                m in reversed(messages)]
    return {"chat_id": chat_id, "messages": msg_list}


@router.post("/{chat_id}/files")
async def upload_file(
        chat_id: int,
        file: UploadFile = File(...),
        username: str = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Отправка файла чанками"""
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    is_admin = user.is_admin if user else False

    if not is_admin:
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
               "timestamp": new_msg.timestamp}
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
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()

    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")

    # Удалить может либо автор, либо АДМИН
    if msg.sender != username and not user.is_admin:
        raise HTTPException(status_code=403, detail="Это не ваше сообщение")

    chat_id = msg.chat_id
    file_path = msg.file_path

    await db.delete(msg)
    await db.commit()

    # Физически удаляем файл с диска
    if file_path and os.path.exists(file_path):
        os.remove(file_path)

    # Уведомляем всех в чате через сокет
    members = (await db.execute(select(ChatMember.username).where(ChatMember.chat_id == chat_id))).scalars().all()
    for member in members:
        await manager.send_to_user(member, {"action": "msg_deleted", "chat_id": chat_id, "msg_id": msg_id})

    return {"status": "ok"}