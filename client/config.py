import os
import sys
import json
import platform
from pathlib import Path

# Импорты для генерации иконок и безопасного хранения паролей
from PIL import Image, ImageDraw
import keyring


# --- УМНЫЕ ПУТИ ДЛЯ ОС ---
def get_app_data_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        return Path(app_data) / "SimpleMessenger"
    elif system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "SimpleMessenger"
    else:  # Linux
        return Path.home() / ".config" / "SimpleMessenger"


APP_DIR = get_app_data_dir()
APP_DIR.mkdir(parents=True, exist_ok=True)

ASSETS_DIR = APP_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

SETTINGS_FILE = APP_DIR / "settings.json"
ICON_PATH = ASSETS_DIR / "icon.png"
UNREAD_ICON_PATH = ASSETS_DIR / "icon_unread.png"
ICO_PATH = ASSETS_DIR / "icon.ico"


# --- АВТОГЕНЕРАЦИЯ ИКОНОК ---
def create_icons_if_needed():
    """Создает базовые иконки приложения, если их еще нет"""
    if not ICON_PATH.exists():
        img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(43, 43, 43))
        d.text((16, 24), "MSG", fill=(255, 255, 255))
        img.save(ICON_PATH)

    if not UNREAD_ICON_PATH.exists():
        img = Image.open(ICON_PATH).copy()
        ImageDraw.Draw(img).ellipse((44, 4, 64, 24), fill=(255, 0, 0))
        img.save(UNREAD_ICON_PATH)

    # Формат .ico для уведомлений Центра Windows
    if not ICO_PATH.exists():
        img = Image.open(ICON_PATH)
        img.save(ICO_PATH, format="ICO", sizes=[(64, 64)])


# --- НАСТРОЙКИ И БЕЗОПАСНОСТЬ ---
def load_settings():
    default_settings = {
        "host": "",
        "username": "",
        "password": "",
        "auto_login": False,
        "auto_start": False,
        "notify_always": True
    }

    # 1. Читаем безопасные настройки (без пароля)
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                default_settings.update(json.load(f))
        except Exception as e:
            print(f"Ошибка чтения настроек: {e}")

    # 2. Безопасно достаем пароль из хранилища ОС
    if default_settings.get("auto_login") and default_settings.get("username"):
        try:
            saved_password = keyring.get_password("SimpleMessenger", default_settings["username"])
            if saved_password:
                default_settings["password"] = saved_password
        except Exception as e:
            print(f"Ошибка чтения хранилища ключей: {e}")

    return default_settings


def save_settings(settings):
    # Копируем словарь, чтобы не удалить пароль из оперативной памяти программы
    to_save = settings.copy()

    # Вытаскиваем пароль — его НЕЛЬЗЯ писать в json!
    password = to_save.pop("password", "")
    username = to_save.get("username", "")
    auto_login = to_save.get("auto_login", False)

    # 1. Сохраняем обычные настройки
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=4)

    # 2. Управляем паролем в защищенном хранилище ОС
    try:
        if auto_login and username and password:
            keyring.set_password("SimpleMessenger", username, password)
        elif not auto_login and username:
            # Если юзер выключил автологин, стираем пароль из системы
            try:
                keyring.delete_password("SimpleMessenger", username)
            except keyring.errors.PasswordDeleteError:
                pass  # Пароля там и не было, всё ок
    except Exception as e:
        print(f"Ошибка записи в хранилище ключей: {e}")


# --- АВТОЗАПУСК ---
def set_autostart(enable: bool):
    system = platform.system()
    try:
        if system == "Windows":
            _set_autostart_win(enable)
        elif system == "Darwin":
            _set_autostart_mac(enable)
    except Exception as e:
        print(f"Ошибка автозапуска: {e}")


def _set_autostart_win(enable: bool):
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)
    if enable:
        python_path = sys.executable
        script_path = os.path.abspath(sys.argv[0])
        winreg.SetValueEx(key, "SimpleMessenger", 0, winreg.REG_SZ, f'"{python_path}" "{script_path}"')
    else:
        try:
            winreg.DeleteValue(key, "SimpleMessenger")
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)


def _set_autostart_mac(enable: bool):
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.simplemessenger.plist"
    if enable:
        python_path, script_path = sys.executable, os.path.abspath(sys.argv[0])
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict><key>Label</key><string>com.simplemessenger</string><key>ProgramArguments</key>
<array><string>{python_path}</string><string>{script_path}</string></array>
<key>RunAtLoad</key><true/></dict></plist>"""
        with open(plist_path, "w", encoding="utf-8") as f:
            f.write(plist_content)
    else:
        if plist_path.exists(): os.remove(plist_path)