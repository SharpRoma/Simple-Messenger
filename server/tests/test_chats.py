import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.security import create_access_token
from models.user import User
from models.chat import Chat, ChatMember


async def register_and_get_token(client: AsyncClient, username: str) -> str:
    payload = {
        "username": username,
        "password": "password123",
        "secret": "niir-invite"
    }
    response = await client.post("/api/auth/register", json=payload)
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_get_my_chats_empty(client: AsyncClient):
    token = await register_and_get_token(client, "testuser")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/chats/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "chats" in data
    # Должен быть только один чат - автоматически созданный "Избранное"
    assert len(data["chats"]) == 1
    assert data["chats"][0]["name"] == "Избранное"
    assert data["chats"][0]["type"] == "saved"


@pytest.mark.asyncio
async def test_create_dialog_success(client: AsyncClient, db_session: AsyncSession):
    token1 = await register_and_get_token(client, "user1")
    token2 = await register_and_get_token(client, "user2")

    headers1 = {"Authorization": f"Bearer {token1}"}

    # Создаем диалог с user2
    payload = {"target_username": "user2"}
    response = await client.post("/api/chats/dialog", json=payload, headers=headers1)
    assert response.status_code == 200
    data = response.json()
    assert "chat_id" in data
    assert data["target"] == "user2"

    # Проверяем, создался ли чат в БД
    chat_id = data["chat_id"]
    chat_result = await db_session.execute(select(Chat).where(Chat.id == chat_id))
    chat = chat_result.scalar_one_or_none()
    assert chat is not None
    assert chat.type == "dialog"

    # Участниками должны быть оба пользователя
    members_result = await db_session.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id)
    )
    members = [m.username for m in members_result.scalars().all()]
    assert "user1" in members
    assert "user2" in members


@pytest.mark.asyncio
async def test_create_dialog_nonexistent_user(client: AsyncClient):
    token1 = await register_and_get_token(client, "user1")
    headers1 = {"Authorization": f"Bearer {token1}"}

    payload = {"target_username": "nonexistent"}
    response = await client.post("/api/chats/dialog", json=payload, headers=headers1)
    assert response.status_code == 404
    assert response.json()["detail"] == "Пользователь найден" or "Пользователь не найден" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_group_success(client: AsyncClient, db_session: AsyncSession):
    token = await register_and_get_token(client, "creator")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"name": "Test Group"}
    response = await client.post("/api/chats/group", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "chat_id" in data
    assert data["name"] == "Test Group"

    # Проверяем в базе
    chat_id = data["chat_id"]
    chat_result = await db_session.execute(select(Chat).where(Chat.id == chat_id))
    chat = chat_result.scalar_one_or_none()
    assert chat is not None
    assert chat.type == "group"
    assert chat.name == "Test Group"


@pytest.mark.asyncio
async def test_add_member_to_group(client: AsyncClient, db_session: AsyncSession):
    token_creator = await register_and_get_token(client, "creator")
    token_member = await register_and_get_token(client, "member1")

    headers_creator = {"Authorization": f"Bearer {token_creator}"}

    # Создаем группу
    group_res = await client.post("/api/chats/group", json={"name": "My Group"}, headers=headers_creator)
    chat_id = group_res.json()["chat_id"]

    # Добавляем member1 в группу
    add_payload = {"username": "member1"}
    response = await client.post(f"/api/chats/{chat_id}/members", json=add_payload, headers=headers_creator)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Проверяем в базе
    members_result = await db_session.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id)
    )
    members = [m.username for m in members_result.scalars().all()]
    assert "creator" in members
    assert "member1" in members
