import logging
import os
from logging.handlers import RotatingFileHandler
from core.config import BASE_DIR


def setup_logger():
    """Настраивает корневой логгер для записи в консоль и в файл с ротацией"""
    logs_dir = BASE_DIR / "logs"
    os.makedirs(logs_dir, exist_ok=True)
    log_file = str(logs_dir / "server.log")

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
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Перенаправляем логи uvicorn в наш файл
    log_file_path = str(logs_dir / "server.log")
    for uvicorn_logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uv_logger = logging.getLogger(uvicorn_logger_name)
        # Добавляем файловый обработчик
        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        uv_logger.addHandler(file_handler)
