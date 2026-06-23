import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
async def test_upload_and_get_public_key(client: AsyncClient, db_session: AsyncSession):
    token = await register_and_get_token(client, "alice")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Загружаем публичный ключ
    pub_key_data = "AliceFakeRSAPublicKeyPEM"
    response = await client.post("/api/auth/public-key", json={"public_key": pub_key_data}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Проверяем в БД напрямую
    db_result = await db_session.execute(select(User).where(User.username == "alice"))
    user = db_result.scalar_one()
    assert user.public_key == pub_key_data

    # 2. Скачиваем публичный ключ другим пользователем (bob)
    bob_token = await register_and_get_token(client, "bob")
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    response = await client.get("/api/users/alice/public-key", headers=bob_headers)
    assert response.status_code == 200
    assert response.json()["public_key"] == pub_key_data

    # Проверка на несуществующего пользователя
    response = await client.get("/api/users/nonexistent/public-key", headers=bob_headers)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_create_secret_chat_success(client: AsyncClient, db_session: AsyncSession):
    token_alice = await register_and_get_token(client, "alice2")
    token_bob = await register_and_get_token(client, "bob2")

    headers_alice = {"Authorization": f"Bearer {token_alice}"}

    # Создаем секретный чат
    payload = {
        "target_username": "bob2",
        "encrypted_key_sender": "AliceEncryptedSymmetricKey",
        "encrypted_key_recipient": "BobEncryptedSymmetricKey"
    }
    response = await client.post("/api/chats/secret", json=payload, headers=headers_alice)
    assert response.status_code == 200
    data = response.json()
    assert "chat_id" in data
    assert data["target"] == "bob2"

    chat_id = data["chat_id"]

    # Проверяем тип чата в БД
    db_chat_res = await db_session.execute(select(Chat).where(Chat.id == chat_id))
    chat = db_chat_res.scalar_one_or_none()
    assert chat is not None
    assert chat.type == "secret"

    # Проверяем encrypted_key участников
    db_members_res = await db_session.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id).order_by(ChatMember.username)
    )
    members = db_members_res.scalars().all()
    assert len(members) == 2
    assert members[0].username == "alice2"
    assert members[0].encrypted_key == "AliceEncryptedSymmetricKey"
    assert members[1].username == "bob2"
    assert members[1].encrypted_key == "BobEncryptedSymmetricKey"

    # Получаем список чатов для alice2
    resp_alice = await client.get("/api/chats/", headers=headers_alice)
    assert resp_alice.status_code == 200
    chats_alice = resp_alice.json()["chats"]
    # Должен быть Избранное и секретный чат
    secret_chat_info = [c for c in chats_alice if c["type"] == "secret"][0]
    assert secret_chat_info["encrypted_key"] == "AliceEncryptedSymmetricKey"

    # Получаем список чатов для bob2
    headers_bob = {"Authorization": f"Bearer {token_bob}"}
    resp_bob = await client.get("/api/chats/", headers=headers_bob)
    assert resp_bob.status_code == 200
    chats_bob = resp_bob.json()["chats"]
    secret_chat_info_bob = [c for c in chats_bob if c["type"] == "secret"][0]
    assert secret_chat_info_bob["encrypted_key"] == "BobEncryptedSymmetricKey"
