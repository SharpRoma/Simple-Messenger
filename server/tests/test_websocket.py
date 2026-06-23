import pytest
from fastapi.testclient import TestClient
from main import app
from core.database import get_db
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_websocket_connection_unauthorized():
    client = TestClient(app)
    # Хендшейк должен завершиться с ошибкой 1008 при невалидном токене
    with pytest.raises(Exception):
        with client.websocket_connect("/ws?token=invalid_token") as ws:
            pass


@pytest.mark.asyncio
async def test_websocket_flow():
    # Настраиваем зависимость тестовой БД
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)

    # 1. Регистрируем пользователя
    reg_res = client.post("/api/auth/register", json={
        "username": "user1",
        "password": "password123",
        "secret": "niir-invite"
    })
    assert reg_res.status_code == 200
    token1 = reg_res.json()["access_token"]

    # 2. Подключаемся через WebSocket
    with client.websocket_connect(f"/ws?token={token1}") as ws:
        # Проверяем получение бродкаста статуса пользователя
        status_msg = ws.receive_json()
        assert status_msg["action"] == "status"
        assert status_msg["username"] == "user1"
        assert status_msg["status"] == "online"

        # 3. Отправляем typing-уведомление в личный чат (Избранное имеет ID 1)
        ws.send_json({
            "action": "typing",
            "chat_id": 1
        })

        # 4. Отправляем текстовое сообщение в свой же чат (Избранное)
        ws.send_json({
            "action": "send_msg",
            "chat_id": 1,
            "text": "Hello World!"
        })

        # 5. Убеждаемся, что получили сообщение обратно (рассылка участникам чата)
        msg = ws.receive_json()
        assert msg["action"] == "new_msg"
        assert msg["chat_id"] == 1
        assert msg["message"]["sender"] == "user1"
        assert msg["message"]["text"] == "Hello World!"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_websocket_message_edit():
    # Настраиваем зависимость тестовой БД
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)

    # 1. Регистрируем пользователя
    reg_res = client.post("/api/auth/register", json={
        "username": "user2",
        "password": "password123",
        "secret": "niir-invite"
    })
    assert reg_res.status_code == 200
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Подключаемся через WebSocket
    with client.websocket_connect(f"/ws?token={token}") as ws:
        # Пропускаем приветственный статус
        status_msg = ws.receive_json()
        assert status_msg["action"] == "status"

        # Получаем список чатов через API
        chats_res = client.get("/api/chats/", headers=headers)
        assert chats_res.status_code == 200
        chats = chats_res.json()["chats"]
        chat_id = chats[0]["id"]

        # 3. Отправляем текстовое сообщение в свой же чат (Избранное)
        ws.send_json({
            "action": "send_msg",
            "chat_id": chat_id,
            "text": "Original text"
        })

        # Получаем подтверждение отправки
        msg_resp = ws.receive_json()
        assert msg_resp["action"] == "new_msg"
        msg_id = msg_resp["message"]["id"]
        assert msg_resp["message"]["text"] == "Original text"

        # 4. Редактируем сообщение через REST API
        edit_res = client.put(
            f"/api/messages/{msg_id}",
            data={"text": "Edited text", "delete_file": "false"},
            headers=headers
        )
        assert edit_res.status_code == 200
        assert edit_res.json()["status"] == "ok"
        assert edit_res.json()["message"]["text"] == "Edited text"

        # 5. Проверяем получение WebSocket-события "msg_edited"
        edited_ws_msg = ws.receive_json()
        assert edited_ws_msg["action"] == "msg_edited"
        assert edited_ws_msg["chat_id"] == chat_id
        assert edited_ws_msg["message"]["id"] == msg_id
        assert edited_ws_msg["message"]["text"] == "Edited text"
        assert edited_ws_msg["message"]["updated_at"] is not None

    app.dependency_overrides.clear()

