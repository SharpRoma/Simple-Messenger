import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.user import User
from models.chat import ChatMember
from models.message import Message



async def is_user_in_chat(db: AsyncSession, chat_id: int, username: str) -> bool:
    """Проверяет, состоит ли пользователь в чате"""
    member_check = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.username == username)
    )
    return member_check.scalar_one_or_none() is not None


async def create_message(db: AsyncSession, chat_id: int, sender: str, text: str) -> Message:
    """Создает новое сообщение и сохраняет его в БД"""
    new_msg = Message(
        chat_id=chat_id,
        sender=sender,
        text=text,
        timestamp=int(time.time())
    )
    db.add(new_msg)
    await db.commit()
    await db.refresh(new_msg)
    return new_msg


async def get_chat_member_usernames(db: AsyncSession, chat_id: int) -> list[str]:
    """Возвращает список логинов всех участников чата"""
    result = await db.execute(select(ChatMember.username).where(ChatMember.chat_id == chat_id))
    return list(result.scalars().all())


async def update_user_last_seen(db: AsyncSession, username: str, timestamp: int):
    """Обновляет время последнего входа пользователя в систему"""
    db_user = await db.get(User, username)
    if db_user:
        db_user.last_seen = timestamp
        await db.commit()
