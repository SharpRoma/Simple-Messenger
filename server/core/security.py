import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from .config import settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    # Устанавливаем время жизни токена
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})

    # Создаем криптографически подписанный токен
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)