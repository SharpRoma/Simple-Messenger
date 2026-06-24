import os
import platform
import subprocess
import webbrowser
import logging

logger = logging.getLogger("messenger.utils")


def open_file_in_default_app(filepath: str):
    """Открывает файл в приложении по умолчанию для данной ОС."""
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", filepath])
        elif system == "Windows":
            os.startfile(filepath)
        else:
            subprocess.run(["xdg-open", filepath])
    except Exception as err:
        logger.error(f"Failed to open file: {err}")


def open_url_in_browser(url: str):
    """Открывает веб-ссылку в браузере по умолчанию."""
    try:
        webbrowser.open(url)
    except Exception as err:
        logger.error(f"Failed to open URL in browser: {err}")


def open_folder_and_select_file(filepath: str):
    """Открывает папку с файлом и выделяет этот файл в проводнике/файловом менеджере."""
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", "-R", filepath])
        elif system == "Windows":
            subprocess.run(["explorer", "/select,", os.path.normpath(filepath)])
        else:
            subprocess.run(["xdg-open", os.path.dirname(filepath)])
    except Exception as err:
        logger.error(f"Failed to open folder and select file: {err}")
