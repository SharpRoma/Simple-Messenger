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
