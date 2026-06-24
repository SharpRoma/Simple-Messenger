import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем абсолютный путь к папке server
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    server_secret: str
    admin_secret: str
    jwt_secret_key: str

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    db_host: str
    db_port: str = "5432"
    db_user: str
    db_password: str
    db_name: str

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")


settings = Settings()