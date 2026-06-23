import pytest
from fastapi.testclient import TestClient
from main import app
from core.database import get_db
from tests.conftest import TestingSessionLocal

@pytest.mark.asyncio
async def test_user_and_message_search():
    # Настраиваем зависимость тестовой БД
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)

    # 1. Регистрируем двух пользователей
    reg_res1 = client.post("/api/auth/register", json={
        "username": "alice",
        "password": "password123",
        "secret": "niir-invite"
    })
    assert reg_res1.status_code == 200
    token1 = reg_res1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    reg_res2 = client.post("/api/auth/register", json={
        "username": "bob",
        "password": "password123",
        "secret": "niir-invite"
    })
    assert reg_res2.status_code == 200
    token2 = reg_res2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # 2. Тестируем поиск пользователей
    # Alice ищет "bo" (должен найтись bob)
    search_res = client.get("/api/users/search?query=bo", headers=headers1)
    assert search_res.status_code == 200
    assert "bob" in search_res.json()["users"]
    # Alice не должна видеть себя в результатах
    assert "alice" not in search_res.json()["users"]

    # 3. Тестируем поиск сообщений
    # Получаем список чатов Alice (Избранное)
    chats_res = client.get("/api/chats/", headers=headers1)
    assert chats_res.status_code == 200
    chats = chats_res.json()["chats"]
    alice_saved_chat_id = chats[0]["id"]

    # Подключаем Alice к WebSocket для отправки сообщений
    with client.websocket_connect(f"/ws?token={token1}") as ws:
        status_msg = ws.receive_json()
        assert status_msg["action"] == "status"

        # Отправляем сообщение 1
        ws.send_json({
            "action": "send_msg",
            "chat_id": alice_saved_chat_id,
            "text": "Hello world from Alice!"
        })
        ws.receive_json() # Пропускаем подтверждение

        # Отправляем сообщение 2
        ws.send_json({
            "action": "send_msg",
            "chat_id": alice_saved_chat_id,
            "text": "Flet is a great python UI framework"
        })
        ws.receive_json() # Пропускаем подтверждение

        # Отправляем сообщение 3 с прикрепленным файлом (через REST)
        import io
        file_content = b"Some file content"
        file_data = {"file": ("report_q2.pdf", io.BytesIO(file_content), "application/pdf")}
        upload_res = client.post(f"/api/messages/{alice_saved_chat_id}/files", files=file_data, headers=headers1)
        assert upload_res.status_code == 200
        ws.receive_json() # Пропускаем оповещение о файле

    # 4. Выполняем поиск по тексту сообщения
    search_msg_res = client.get(f"/api/messages/{alice_saved_chat_id}/search?query=great", headers=headers1)
    assert search_msg_res.status_code == 200
    found_messages = search_msg_res.json()["messages"]
    assert len(found_messages) == 1
    assert "great python UI framework" in found_messages[0]["text"]

    # 5. Выполняем поиск по имени файла
    search_file_res = client.get(f"/api/messages/{alice_saved_chat_id}/search?query=report", headers=headers1)
    assert search_file_res.status_code == 200
    found_files = search_file_res.json()["messages"]
    assert len(found_files) == 1
    assert found_files[0]["file_name"] == "report_q2.pdf"

    # 6. Проверяем ограничение доступа (Bob пытается искать в чате Alice)
    forbidden_res = client.get(f"/api/messages/{alice_saved_chat_id}/search?query=hello", headers=headers2)
    assert forbidden_res.status_code == 403

    app.dependency_overrides.clear()
