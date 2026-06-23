import uuid
import time
import jwt
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from core.database import get_db
from core.config import settings
from core.security import hash_password, verify_password, create_access_token
from models.user import User
from models.chat import Chat, ChatMember
from models.session import UserSession
from schemas.auth import UserRegister, UserLogin, TokenResponse, UserReset
from api.dependencies import get_current_user
from api.websockets import manager

# Создаем роутер
router = APIRouter(prefix="/auth", tags=["Авторизация"])


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister, request: Request, db: AsyncSession = Depends(get_db)):
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

    # 5. Создаем сессию в БД
    token_id = uuid.uuid4().hex
    ip_addr = request.client.host if request.client else "127.0.0.1"
    new_session = UserSession(
        username=new_user.username,
        token_id=token_id,
        ip_address=ip_addr,
        created_at=int(time.time())
    )
    db.add(new_session)

    await db.commit()  # Сохраняем всё в БД

    # Выдаем токен для входа
    token = create_access_token({"sub": new_user.username, "jti": token_id})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")

    # Создаем сессию в БД
    token_id = uuid.uuid4().hex
    ip_addr = request.client.host if request.client else "127.0.0.1"
    new_session = UserSession(
        username=user.username,
        token_id=token_id,
        ip_address=ip_addr,
        created_at=int(time.time())
    )
    db.add(new_session)
    await db.commit()

    token = create_access_token({"sub": user.username, "jti": token_id})
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


@router.get("/sessions")
async def get_sessions(
    request: Request,
    username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.query_params.get("token")

    current_jti = None
    if token:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            current_jti = payload.get("jti")
        except Exception:
            pass

    result = await db.execute(
        select(UserSession).where(UserSession.username == username).order_by(UserSession.created_at.desc())
    )
    sessions = result.scalars().all()

    return {
        "sessions": [
            {
                "id": s.id,
                "ip_address": s.ip_address,
                "created_at": s.created_at,
                "is_current": s.token_id == current_jti
            }
            for s in sessions
        ]
    }


@router.post("/sessions/terminate-others")
async def terminate_others(
    request: Request,
    username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.query_params.get("token")

    current_jti = None
    if token:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            current_jti = payload.get("jti")
        except Exception:
            pass

    if not current_jti:
        raise HTTPException(status_code=400, detail="Неверная сессия")

    # Удаляем другие сессии
    await db.execute(
        delete(UserSession).where(
            UserSession.username == username,
            UserSession.token_id != current_jti
        )
    )
    await db.commit()

    # Закрываем сокеты других сессий
    await manager.disconnect_other_sessions(username, current_jti)

    return {"status": "ok", "msg": "Другие сеансы успешно завершены"}