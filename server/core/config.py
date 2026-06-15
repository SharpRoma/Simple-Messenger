import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Секреты безопасности (обязательны в .env)
    server_secret: str
    jwt_secret_key: str
    admin_password: str

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # Токен живет 7 дней

    # Настройки PostgreSQL
    db_host: str
    db_port: str = "5432"
    db_user: str
    db_password: str
    db_name: str

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()