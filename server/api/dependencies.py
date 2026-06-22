import jwt
from fastapi import HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


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


async def get_current_user(request: Request) -> str:
    """Извлекает логин из JWT токена (из заголовка или URL)"""
    # 1. Сначала ищем токен в стандартном заголовке (для REST API)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        # 2. Если в заголовке нет, ищем прямо в ссылке (для картинок во Flet)
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Отсутствует токен авторизации")

    return get_username_from_token(token)