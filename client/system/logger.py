import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(app_dir: Path):
    """Настраивает корневой логгер клиента для записи в консоль и в файл с ротацией"""
    logs_dir = app_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not root_logger.handlers:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

        # Консольный вывод
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # Вывод в файл (ротация при 5 МБ, храним до 3 бэкапов)
        file_handler = RotatingFileHandler(
            logs_dir / "client.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
