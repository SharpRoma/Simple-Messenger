from sqlalchemy import Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # 'global', 'dialog', 'saved'

class ChatMember(Base):
    __tablename__ = "chat_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # ondelete="CASCADE" значит, что если удалить чат, то все его участники удалятся из этой таблицы
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    username: Mapped[str] = mapped_column(ForeignKey("users.username", ondelete="CASCADE"))

    # Запрещаем добавлять одного юзера в один чат дважды
    __table_args__ = (UniqueConstraint('chat_id', 'username', name='_chat_user_uc'),)