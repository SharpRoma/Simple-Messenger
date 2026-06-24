import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rate_limiting_login(client: AsyncClient):
    payload = {
        "username": "nonexistent",
        "password": "wrongpassword"
    }

    # Делаем 5 запросов (лимит 5 в минуту)
    for _ in range(5):
        response = await client.post("/api/auth/login", json=payload)
        # Они должны возвращать обычную ошибку авторизации (400)
        assert response.status_code == 400
        assert response.json()["detail"] == "Неверный логин или пароль"

    # 6-й запрос должен заблокироваться с кодом 429
    response_blocked = await client.post("/api/auth/login", json=payload)
    assert response_blocked.status_code == 429
    assert "Слишком много запросов" in response_blocked.json()["detail"]
