import pytest
from fastapi.testclient import TestClient
from main import app
from core.database import get_db
from tests.conftest import TestingSessionLocal

@pytest.mark.asyncio
async def test_read_status_flow():
    # Настраиваем зависимость тестовой БД
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)

    # 1. Регистрируем двух пользователей (Alice и Bob)
    reg_res1 = client.post("/api/auth/register", json={
        "username": "user_a",
        "password": "password123",
        "secret": "niir-invite"
    })
    assert reg_res1.status_code == 200
    token_a = reg_res1.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    reg_res2 = client.post("/api/auth/register", json={
        "username": "user_b",
        "password": "password123",
        "secret": "niir-invite"
    })
    assert reg_res2.status_code == 200
    token_b = reg_res2.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 2. Создаем диалог между A и B
    create_chat_res = client.post("/api/chats/dialog", json={"target_username": "user_b"}, headers=headers_a)
    assert create_chat_res.status_code == 200
    chat_id = create_chat_res.json()["chat_id"]

    # 3. User A подключается по сокету и отправляет сообщение
    with client.websocket_connect(f"/ws?token={token_a}") as ws_a:
        # Пропускаем приветственный статус
        ws_a.receive_json()

        ws_a.send_json({
            "action": "send_msg",
            "chat_id": chat_id,
            "text": "Hello User B!"
        })
        
        # Получаем эхо-подтверждение о новом сообщении
        new_msg_resp = ws_a.receive_json()
        assert new_msg_resp["action"] == "new_msg"
        assert new_msg_resp["message"]["text"] == "Hello User B!"
        assert new_msg_resp["message"]["is_read"] is False

        # 4. User B запрашивает историю чата (это должно пометить сообщение прочитанным)
        history_res = client.get(f"/api/messages/{chat_id}", headers=headers_b)
        assert history_res.status_code == 200
        messages = history_res.json()["messages"]
        assert len(messages) == 1
        assert messages[0]["text"] == "Hello User B!"
        assert messages[0]["is_read"] is True

        # 5. User A должен получить сокетное уведомление "messages_read"
        read_event = ws_a.receive_json()
        assert read_event["action"] == "messages_read"
        assert read_event["chat_id"] == chat_id

    # 6. Отправка еще одного сообщения, которое Bob прочтет через WebSocket action "read_chat"
    with client.websocket_connect(f"/ws?token={token_a}") as ws_a:
        ws_a.receive_json() # Пропускаем статус
        ws_a.send_json({
            "action": "send_msg",
            "chat_id": chat_id,
            "text": "Are you there?"
        })
        ws_a.receive_json() # Пропускаем эхо-подтверждение

    # Теперь Bob подключается отдельно и читает чат
    with client.websocket_connect(f"/ws?token={token_b}") as ws_b:
        ws_b.receive_json() # Пропускаем статус
        ws_b.send_json({
            "action": "read_chat",
            "chat_id": chat_id
        })
        # Ждем бродкаст о прочтении, чтобы гарантировать запись в БД
        read_event = ws_b.receive_json()
        assert read_event["action"] == "messages_read"

    # Проверяем через REST, что сообщение стало прочитанным
    history_res2 = client.get(f"/api/messages/{chat_id}", headers=headers_a)
    assert history_res2.status_code == 200
    messages2 = history_res2.json()["messages"]
    msg2 = next(m for m in messages2 if m["text"] == "Are you there?")
    assert msg2["is_read"] is True

    app.dependency_overrides.clear()
