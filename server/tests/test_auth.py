import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.user import User
from models.chat import ChatMember, Chat


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient, db_session: AsyncSession):
    # Тест на успешную регистрацию
    payload = {
        "username": "testuser",
        "password": "testpassword",
        "secret": "niir-invite"  # В соответствии с default settings.server_secret
    }
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Проверяем, создалась ли запись в БД
    result = await db_session.execute(select(User).where(User.username == "testuser"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.username == "testuser"

    # Проверяем, создался ли чат "Избранное"
    chat_member_result = await db_session.execute(
        select(ChatMember).where(ChatMember.username == "testuser")
    )
    chat_member = chat_member_result.scalar_one_or_none()
    assert chat_member is not None

    chat_result = await db_session.execute(select(Chat).where(Chat.id == chat_member.chat_id))
    chat = chat_result.scalar_one_or_none()
    assert chat is not None
    assert chat.type == "saved"
    assert chat.name == "Избранное"


@pytest.mark.asyncio
async def test_register_user_wrong_secret(client: AsyncClient):
    payload = {
        "username": "testuser",
        "password": "testpassword",
        "secret": "wrong-invite"
    }
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Неверный секретный код сервера"


@pytest.mark.asyncio
async def test_register_duplicate_user(client: AsyncClient):
    payload = {
        "username": "testuser",
        "password": "testpassword",
        "secret": "niir-invite"
    }
    response1 = await client.post("/api/auth/register", json=payload)
    assert response1.status_code == 200

    response2 = await client.post("/api/auth/register", json=payload)
    assert response2.status_code == 400
    assert response2.json()["detail"] == "Пользователь уже существует"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # Сначала регистрируемся
    register_payload = {
        "username": "testuser",
        "password": "testpassword",
        "secret": "niir-invite"
    }
    await client.post("/api/auth/register", json=register_payload)

    # Входим
    login_payload = {
        "username": "testuser",
        "password": "testpassword"
    }
    response = await client.post("/api/auth/login", json=login_payload)
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    login_payload = {
        "username": "nonexistent",
        "password": "wrongpassword"
    }
    response = await client.post("/api/auth/login", json=login_payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Неверный логин или пароль"


@pytest.mark.asyncio
async def test_reset_password_success(client: AsyncClient, db_session: AsyncSession):
    # Регистрируем пользователя
    register_payload = {
        "username": "testuser",
        "password": "testpassword",
        "secret": "niir-invite"
    }
    await client.post("/api/auth/register", json=register_payload)

    # Сбрасываем пароль с использованием ADMIN_SECRET (niir-reset)
    reset_payload = {
        "username": "testuser",
        "new_password": "newpassword123",
        "secret": "niir-reset"
    }
    response = await client.post("/api/auth/reset-password", json=reset_payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Пытаемся войти со старым паролем
    login_payload_old = {
        "username": "testuser",
        "password": "testpassword"
    }
    response_old = await client.post("/api/auth/login", json=login_payload_old)
    assert response_old.status_code == 400

    # Входим с новым паролем
    login_payload_new = {
        "username": "testuser",
        "password": "newpassword123"
    }
    response_new = await client.post("/api/auth/login", json=login_payload_new)
    assert response_new.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_wrong_secret(client: AsyncClient):
    # Пытаемся использовать инвайт-код (niir-invite) вместо админ-секрета
    reset_payload = {
        "username": "testuser",
        "new_password": "newpassword123",
        "secret": "niir-invite"
    }
    response = await client.post("/api/auth/reset-password", json=reset_payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Неверный секретный код администратора"

