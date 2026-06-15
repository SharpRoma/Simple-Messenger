from fastapi import FastAPI
from contextlib import asynccontextmanager

from core.database import init_db
from api.routes import auth, chat_ws, chats, messages

# Lifespan: код, который выполняется один раз при запуске сервера
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Подключение к базе данных и создание таблиц...")
    await init_db()
    print("База данных готова!")
    yield
    print("Сервер выключается...")

# Создаем само приложение FastAPI
app = FastAPI(
    title="Simple Messenger API",
    description="REST API и WebSockets для мессенджера",
    version="2.0.0",
    lifespan=lifespan
)

# Подключаем REST API ручки
app.include_router(auth.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(messages.router, prefix="/api")

# Подключаем WebSocket ручку
app.include_router(chat_ws.router)


@app.get("/", tags=["Служебные"])
async def root():
    return {"message": "Messenger Server is running! Go to /docs for Swagger UI"}