import jwt
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.config import settings
from core.database import get_db
from models.session import UserSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def decode_access_token(token: str) -> dict:
    """Декодирует JWT токен и возвращает его payload"""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен"
        )


def get_username_from_token(token: str) -> str:
    """Расшифровывает токен и возвращает логин пользователя (для совместимости)"""
    payload = decode_access_token(token)
    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен не содержит пользователя"
        )
    return username


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> str:
    """Извлекает логин из JWT токена и проверяет активность сессии в БД"""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Отсутствует токен авторизации")

    payload = decode_access_token(token)
    username = payload.get("sub")
    jti = payload.get("jti")

    if not username or not jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен")

    # Проверяем, существует ли активная сессия в базе данных
    result = await db.execute(
        select(UserSession).where(
            UserSession.username == username,
            UserSession.token_id == jti
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия завершена или не существует"
        )

    return username