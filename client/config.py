import os
import sys
import json
import platform
import shutil
from pathlib import Path

from PIL import Image, ImageDraw
import keyring


# --- ВЕРСИЯ ПРИЛОЖЕНИЯ ---
APP_VERSION = "1.1.1"


# --- УМНЫЕ ПУТИ ДЛЯ PYINSTALLER ---
# Когда Flet собирает .exe, он прячет assets во временную папку sys._MEIPASS
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

LOCAL_ASSETS_DIR = BASE_DIR / "assets"

# --- УМНЫЕ ПУТИ ДЛЯ ОС (Где храним данные) ---
def get_app_data_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        return Path(app_data) / "SimpleMessenger"
    elif system == "Darwin": # macOS
        return Path.home() / "Library" / "Application Support" / "SimpleMessenger"
    else: # Linux
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
    custom_icon = LOCAL_ASSETS_DIR / "icon.png"

    # Файл-маркер, чтобы понимать, обновляли ли мы иконки для текущей версии
    version_file = ASSETS_DIR / "version.txt"
    need_update = not version_file.exists() or version_file.read_text().strip() != APP_VERSION

    if not need_update and ICON_PATH.exists():
        return  # Иконки актуальны, ничего не делаем

    if need_update:
        for p in [ICON_PATH, UNREAD_ICON_PATH, ICO_PATH]:
            if p.exists(): p.unlink()

    try:
        # 1. Делаем круглую иконку из исходников
        if custom_icon.exists():
            img = Image.open(custom_icon).convert("RGBA")
            w, h = img.size
            min_dim = min(w, h)
            left, top = (w - min_dim) / 2, (h - min_dim) / 2
            right, bottom = (w + min_dim) / 2, (h + min_dim) / 2
            img = img.crop((left, top, right, bottom))

            mask = Image.new("L", img.size, 0)
            ImageDraw.Draw(mask).ellipse((0, 0, img.size[0], img.size[1]), fill=255)

            circular_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
            circular_img.paste(img, (0, 0), mask=mask)
            circular_img.save(ICON_PATH)

        # 2. Либо рисуем заглушку
        else:
            img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse((4, 4, 60, 60), fill=(43, 43, 43))
            d.text((16, 24), "MSG", fill=(255, 255, 255))
            img.save(ICON_PATH)

        # 3. Рисуем кружок уведомлений
        if ICON_PATH.exists():
            img = Image.open(ICON_PATH).convert("RGBA")
            unread_img = img.copy()
            d = ImageDraw.Draw(unread_img)
            w, h = unread_img.size

            badge_bbox = (w * 0.50, h * 0.02, w * 0.98, h * 0.50)
            d.ellipse(badge_bbox, fill=(255, 0, 0), outline=(255, 255, 255), width=max(2, int(w * 0.04)))
            unread_img.save(UNREAD_ICON_PATH)

            img.save(ICO_PATH, format="ICO", sizes=[(64, 64), (128, 128), (256, 256)])

        # Записываем версию, чтобы больше не перерисовывать до следующего обновления
        version_file.write_text(APP_VERSION)
    except Exception as e:
        print(f"Ошибка при обработке иконок: {e}")


# --- НАСТРОЙКИ И БЕЗОПАСНОСТЬ ---
def load_settings():
    default_settings = {
        "host": "",
        "port": "8888",
        "username": "",
        "password": "",
        "auto_login": False,
        "auto_start": False,
        "notify_always": True
    }

    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                default_settings.update(json.load(f))
        except Exception as e:
            print(f"Ошибка чтения настроек: {e}")

    if default_settings.get("auto_login") and default_settings.get("username"):
        try:
            saved_password = keyring.get_password("SimpleMessenger", default_settings["username"])
            if saved_password:
                default_settings["password"] = saved_password
        except Exception as e:
            pass

    return default_settings


def save_settings(settings):
    to_save = settings.copy()
    password = to_save.pop("password", "")
    username = to_save.get("username", "")
    auto_login = to_save.get("auto_login", False)

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=4)

    try:
        if auto_login and username and password:
            keyring.set_password("SimpleMessenger", username, password)
        elif not auto_login and username:
            try:
                keyring.delete_password("SimpleMessenger", username)
            except keyring.errors.PasswordDeleteError:
                pass
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
        pass


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