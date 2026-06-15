import jwt
from fastapi import HTTPException, status
from core.config import settings

from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends

def get_username_from_token(token: str) -> str:
    """Расшифровывает токен и возвращает логин пользователя"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise ValueError("Токен не содержит пользователя")
        return username
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен"
        )

# Указываем Swagger где брать токен (по какому URL логиниться)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Извлекает username из JWT токена при каждом HTTP-запросе"""
    return get_username_from_token(token)