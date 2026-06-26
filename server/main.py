import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

from core.database import init_db
from core.logger import setup_logger
from api.routes import auth, chat_ws, chats, messages, users

# Инициализируем логирование
setup_logger()
logger = logging.getLogger("messenger.main")

# Lifespan: код, который выполняется один раз при запуске сервера
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Подключение к базе данных и создание таблиц...")
    await init_db()
    logger.info("База данных готова!")
    yield
    logger.info("Сервер выключается...")

# Создаем само приложение FastAPI
app = FastAPI(
    title="Simple Messenger API",
    description="REST API и WebSockets для мессенджера",
    version="1.3",
    lifespan=lifespan
)

# Подключаем REST API ручки
app.include_router(auth.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(users.router, prefix="/api")

# Подключаем WebSocket ручку
app.include_router(chat_ws.router)


@app.get("/", tags=["Служебные"])
async def root():
    return {"message": "Messenger Server is running! Go to /docs for Swagger UI"}