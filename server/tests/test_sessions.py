import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.session import UserSession

@pytest.mark.asyncio
async def test_session_lifecycle(client: AsyncClient, db_session: AsyncSession):
    # 1. Регистрируем пользователя
    reg_payload = {
        "username": "sessionuser",
        "password": "sessionpassword",
        "secret": "niir-invite"
    }
    reg_res = await client.post("/api/auth/register", json=reg_payload)
    assert reg_res.status_code == 200
    token1 = reg_res.json()["access_token"]

    # 2. Логинимся второй раз (симуляция входа с другого устройства)
    login_payload = {
        "username": "sessionuser",
        "password": "sessionpassword"
    }
    login_res = await client.post("/api/auth/login", json=login_payload)
    assert login_res.status_code == 200
    token2 = login_res.json()["access_token"]

    # Проверяем, что в БД созданы две сессии
    stmt = select(UserSession).where(UserSession.username == "sessionuser")
    result = await db_session.execute(stmt)
    sessions = result.scalars().all()
    assert len(sessions) == 2

    # 3. Запрашиваем сессии с токеном 1
    headers1 = {"Authorization": f"Bearer {token1}"}
    res1 = await client.get("/api/auth/sessions", headers=headers1)
    assert res1.status_code == 200
    sessions_data1 = res1.json()["sessions"]
    assert len(sessions_data1) == 2
    
    # Один из сеансов должен быть помечен как текущий
    current_count1 = sum(1 for s in sessions_data1 if s["is_current"])
    assert current_count1 == 1
    
    # 4. Завершаем другие сеансы с токена 2
    headers2 = {"Authorization": f"Bearer {token2}"}
    term_res = await client.post("/api/auth/sessions/terminate-others", headers=headers2)
    assert term_res.status_code == 200
    assert term_res.json()["status"] == "ok"

    # 5. Проверяем, что осталась только одна сессия (для токена 2)
    res2 = await client.get("/api/auth/sessions", headers=headers2)
    assert res2.status_code == 200
    sessions_data2 = res2.json()["sessions"]
    assert len(sessions_data2) == 1
    assert sessions_data2[0]["is_current"] is True

    # 6. Проверяем, что токен 1 теперь недействителен (деавторизован)
    res1_after = await client.get("/api/auth/sessions", headers=headers1)
    assert res1_after.status_code == 401
    assert "detail" in res1_after.json()
