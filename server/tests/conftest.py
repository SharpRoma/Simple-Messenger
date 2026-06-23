import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from pathlib import Path

# Используем временный файл базы данных для тестов (абсолютный путь в папке server)
TEST_DB_FILE = str(Path(__file__).resolve().parent.parent / "test_db.sqlite")
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Переопределяем фабрику сессий до импорта приложения и роутов
import core.database
core.database.async_session_maker = TestingSessionLocal

from main import app
from core.database import get_db
from models import Base


@pytest.fixture(scope="function", autouse=True)
async def setup_db():
    """Создает таблицы перед тестом и удаляет их после завершения тестов"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def db_session() -> AsyncSession:
    """Фикстура для сессии базы данных"""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncClient:
    """Фикстура для HTTP-клиента с подменой зависимости get_db"""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Используем ASGITransport для работы с AsyncClient в httpx >= 0.27.0
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
