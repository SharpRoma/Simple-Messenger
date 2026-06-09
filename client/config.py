import os
import sys
import json
import platform
from pathlib import Path

# --- УМНЫЕ ПУТИ ДЛЯ ОС ---
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

# --- НАСТРОЙКИ ---
def load_settings():
    default_settings = {
        "host": "127.0.0.1",
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
    return default_settings

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

# --- АВТОЗАПУСК ---
def set_autostart(enable: bool):
    system = platform.system()
    try:
        if system == "Windows": _set_autostart_win(enable)
        elif system == "Darwin": _set_autostart_mac(enable)
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
        try: winreg.DeleteValue(key, "SimpleMessenger")
        except FileNotFoundError: pass
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
        with open(plist_path, "w", encoding="utf-8") as f: f.write(plist_content)
    else:
        if plist_path.exists(): os.remove(plist_path)