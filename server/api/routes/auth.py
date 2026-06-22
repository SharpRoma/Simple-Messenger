from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.config import settings
from core.security import hash_password, verify_password, create_access_token
from models.user import User
from models.chat import Chat, ChatMember
from schemas.auth import UserRegister, UserLogin, TokenResponse, UserReset

# Создаем роутер
router = APIRouter(prefix="/auth", tags=["Авторизация"])


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    # 1. Проверяем секретный код сервера
    if user_data.secret != settings.server_secret:
        raise HTTPException(status_code=400, detail="Неверный секретный код сервера")

    # 2. Проверяем, свободен ли логин
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    # 3. Создаем пользователя
    new_user = User(username=user_data.username, password=hash_password(user_data.password))
    db.add(new_user)

    # 4. Создаем личный чат "Избранное"
    saved_chat = Chat(name="Избранное", type="saved")
    db.add(saved_chat)
    await db.flush()  # Получаем ID созданного чата до коммита
    db.add(ChatMember(chat_id=saved_chat.id, username=new_user.username))

    await db.commit()  # Сохраняем всё в БД

    # Выдаем токен для входа
    token = create_access_token({"sub": new_user.username})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")

    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/reset-password")
async def reset_password(data: UserReset, db: AsyncSession = Depends(get_db)):
    if data.secret != settings.server_secret:
        raise HTTPException(status_code=400, detail="Неверный секретный код сервера")

    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.password = hash_password(data.new_password)
    await db.commit()

    return {"status": "ok", "msg": "Пароль успешно изменен"}