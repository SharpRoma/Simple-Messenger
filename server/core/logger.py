import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger():
    """Настраивает корневой логгер для записи в консоль и в файл с ротацией"""
    os.makedirs("logs", exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Проверяем, не настроены ли уже обработчики (избегаем дублирования)
    if not root_logger.handlers:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

        # Консольный вывод
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # Вывод в файл (ротация при 10 МБ, храним до 5 бэкапов)
        file_handler = RotatingFileHandler(
            "logs/server.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Перенаправляем логи uvicorn в наш файл
    for uvicorn_logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uv_logger = logging.getLogger(uvicorn_logger_name)
        # Добавляем файловый обработчик
        file_handler = RotatingFileHandler(
            "logs/server.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        uv_logger.addHandler(file_handler)
