import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()


class Chat(Base):
    __tablename__ = 'chats'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    symmetric_key = Column(String, nullable=True)

    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey('chats.id', ondelete='CASCADE'), nullable=False)
    sender = Column(String, nullable=False)
    text = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    local_path = Column(String, nullable=True)
    timestamp = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False)

    chat = relationship("Chat", back_populates="messages")


class ClientDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        self.Session = sessionmaker(bind=self.engine)
        self._init_db()

    def _get_conn(self):
        """Возвращает сырое подключение sqlite3 для обратной совместимости (используется в контроллере)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        # Создаем таблицы, если они не существуют
        Base.metadata.create_all(self.engine)
        
        # Безопасные миграции для добавления новых колонок в существующий кэш
        with self.engine.begin() as conn:
            try:
                conn.execute(text("ALTER TABLE chats ADD COLUMN symmetric_key TEXT"))
            except Exception:
                pass  # Колонка уже существует
            try:
                conn.execute(text("ALTER TABLE messages ADD COLUMN local_path TEXT"))
            except Exception:
                pass  # Колонка уже существует

    def save_chats(self, chats: list[dict]):
        with self.Session() as session:
            for chat_dict in chats:
                chat_id = chat_dict["id"]
                chat = session.query(Chat).filter(Chat.id == chat_id).first()
                if chat:
                    chat.name = chat_dict["name"]
                    chat.type = chat_dict["type"]
                    # Сохраняем ключ только если он пришел (эмуляция COALESCE)
                    if "symmetric_key" in chat_dict and chat_dict["symmetric_key"] is not None:
                        chat.symmetric_key = chat_dict["symmetric_key"]
                else:
                    chat = Chat(
                        id=chat_id,
                        name=chat_dict["name"],
                        type=chat_dict["type"],
                        symmetric_key=chat_dict.get("symmetric_key")
                    )
                    session.add(chat)
            session.commit()

    def get_chats(self) -> list[dict]:
        with self.Session() as session:
            chats = session.query(Chat).all()
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "type": c.type,
                    "symmetric_key": c.symmetric_key
                }
                for c in chats
            ]

    def save_messages(self, chat_id: int, messages: list[dict]):
        with self.Session() as session:
            for msg_dict in messages:
                msg_id = msg_dict["id"]
                msg = session.query(Message).filter(Message.id == msg_id).first()
                is_read_val = msg_dict.get("is_read", False)
                
                if msg:
                    msg.chat_id = chat_id
                    msg.sender = msg_dict["sender"]
                    msg.text = msg_dict.get("text")
                    msg.file_name = msg_dict.get("file_name")
                    msg.timestamp = msg_dict["timestamp"]
                    msg.updated_at = msg_dict.get("updated_at")
                    msg.is_read = bool(is_read_val)
                else:
                    msg = Message(
                        id=msg_id,
                        chat_id=chat_id,
                        sender=msg_dict["sender"],
                        text=msg_dict.get("text"),
                        file_name=msg_dict.get("file_name"),
                        local_path=msg_dict.get("local_path"),
                        timestamp=msg_dict["timestamp"],
                        updated_at=msg_dict.get("updated_at"),
                        is_read=bool(is_read_val)
                    )
                    session.add(msg)
            session.commit()

    def get_messages(self, chat_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
        with self.Session() as session:
            messages = (
                session.query(Message)
                .filter(Message.chat_id == chat_id)
                .order_by(Message.timestamp.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            # Возвращаем сообщения в хронологическом порядке (сначала старые)
            return [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "text": m.text,
                    "file_name": m.file_name,
                    "local_path": m.local_path,
                    "timestamp": m.timestamp,
                    "updated_at": m.updated_at,
                    "is_read": m.is_read
                }
                for m in reversed(messages)
            ]

    def get_chat_files(self, chat_id: int) -> list[dict]:
        with self.Session() as session:
            messages = (
                session.query(Message)
                .filter(Message.chat_id == chat_id)
                .filter(Message.file_name.isnot(None))
                .order_by(Message.timestamp.desc())
                .all()
            )
            return [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "text": m.text,
                    "file_name": m.file_name,
                    "local_path": m.local_path,
                    "timestamp": m.timestamp,
                    "updated_at": m.updated_at,
                    "is_read": m.is_read
                }
                for m in messages
            ]

    def get_chat_links(self, chat_id: int) -> list[dict]:
        with self.Session() as session:
            messages = (
                session.query(Message)
                .filter(Message.chat_id == chat_id)
                .filter((Message.text.like('%http://%')) | (Message.text.like('%https://%')))
                .order_by(Message.timestamp.desc())
                .all()
            )
            return [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "text": m.text,
                    "timestamp": m.timestamp
                }
                for m in messages
            ]

    def update_message_local_path(self, msg_id: int, local_path: str):
        with self.Session() as session:
            msg = session.query(Message).filter(Message.id == msg_id).first()
            if msg:
                msg.local_path = local_path
                session.commit()

    def delete_message(self, msg_id: int):
        with self.Session() as session:
            msg = session.query(Message).filter(Message.id == msg_id).first()
            if msg:
                session.delete(msg)
                session.commit()

    def update_message(self, msg_id: int, text: str, file_name: str, updated_at: int, is_read: bool):
        with self.Session() as session:
            msg = session.query(Message).filter(Message.id == msg_id).first()
            if msg:
                msg.text = text
                msg.file_name = file_name
                msg.updated_at = updated_at
                msg.is_read = bool(is_read)
                session.commit()

    def mark_chat_as_read(self, chat_id: int, current_username: str):
        with self.Session() as session:
            session.query(Message).filter(
                Message.chat_id == chat_id,
                Message.sender != current_username
            ).update({Message.is_read: True}, synchronize_session=False)
            session.commit()

    def search_messages(self, chat_id: int, query: str) -> list[dict]:
        with self.Session() as session:
            pattern = f"%{query}%"
            messages = (
                session.query(Message)
                .filter(Message.chat_id == chat_id)
                .filter((Message.text.like(pattern)) | (Message.file_name.like(pattern)))
                .order_by(Message.timestamp.desc())
                .all()
            )
            return [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "text": m.text,
                    "file_name": m.file_name,
                    "local_path": m.local_path,
                    "timestamp": m.timestamp,
                    "updated_at": m.updated_at,
                    "is_read": m.is_read
                }
                for m in reversed(messages)
            ]

    def get_unread_count(self, chat_id: int, current_username: str) -> int:
        with self.Session() as session:
            return session.query(Message).filter(
                Message.chat_id == chat_id,
                Message.sender != current_username,
                Message.is_read == False
            ).count()

    def has_any_unread(self, current_username: str) -> bool:
        with self.Session() as session:
            return session.query(Message).filter(
                Message.sender != current_username,
                Message.is_read == False
            ).limit(1).count() > 0
