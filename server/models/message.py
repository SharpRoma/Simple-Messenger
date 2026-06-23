import time
import os
import logging
from sqlalchemy import Integer, String, ForeignKey, Text, event
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

logger = logging.getLogger("messenger.models.message")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    sender: Mapped[str] = mapped_column(ForeignKey("users.username", ondelete="CASCADE"))

    text: Mapped[str] = mapped_column(Text, nullable=True)
    file_name: Mapped[str] = mapped_column(String, nullable=True)
    file_path: Mapped[str] = mapped_column(String, nullable=True)

    timestamp: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))


@event.listens_for(Message, 'after_delete')
def delete_message_file(mapper, connection, target):
    """Автоматически удаляет файл с диска при удалении сообщения из БД"""
    if target.file_path and os.path.exists(target.file_path):
        try:
            os.remove(target.file_path)
            logger.info(f"Удален файл с диска: {target.file_path}")
        except Exception as e:
            logger.error(f"Не удалось удалить файл {target.file_path}: {e}")