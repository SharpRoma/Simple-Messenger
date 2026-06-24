import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from .config import settings
from models import Base, Chat
from models.user import User
from core.security import hash_password
from core.config import settings

logger = logging.getLogger("messenger.database")

# Создаем асинхронное подключение
engine = create_async_engine(settings.database_url, echo=False)

# Фабрика сессий (через них мы будем делать запросы)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

from sqlalchemy import text

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            # Безопасная миграция колонок для PostgreSQL
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS public_key VARCHAR"))
            await conn.execute(text("ALTER TABLE chat_members ADD COLUMN IF NOT EXISTS encrypted_key VARCHAR"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS updated_at INTEGER"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_read BOOLEAN DEFAULT FALSE"))
        except Exception as e:
            logger.error(f"Failed to run E2EE migrations: {e}")

# Зависимость (Dependency) для FastAPI
# Эта функция будет выдавать сессию БД каждый раз, когда кто-то дергает ручку
async def get_db():
    async with async_session_maker() as session:
        yield session