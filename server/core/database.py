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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        # --- СОЗДАНИЕ АДМИНА ---
        admin_check = await session.execute(select(User).where(User.username == "admin"))
        if not admin_check.scalar_one_or_none():
            admin_user = User(
                username="admin",
                password=hash_password(settings.admin_password),
                is_admin=True
            )
            session.add(admin_user)
            await session.commit()
            logger.info("Пользователь 'admin' успешно создан")

# Зависимость (Dependency) для FastAPI
# Эта функция будет выдавать сессию БД каждый раз, когда кто-то дергает ручку
async def get_db():
    async with async_session_maker() as session:
        yield session