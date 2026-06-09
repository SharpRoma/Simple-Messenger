import os
import sys
import json
import platform
from pathlib import Path

SETTINGS_FILE = "settings.json"


def load_settings():
    """Загружает настройки из файла или возвращает дефолтные"""
    default_settings = {
        "host": "127.0.0.1",
        "username": "",
        "password": "",
        "auto_login": True,
        "auto_start": False,
        "notify_always": True  # False = только закрытые чаты, True = всегда
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_settings.update(data)
        except Exception as e:
            print(f"Ошибка чтения настроек: {e}")
    return default_settings


def save_settings(settings):
    """Сохраняет настройки в JSON"""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)


def set_autostart(enable: bool):
    """Кроссплатформенный автозапуск"""
    system = platform.system()
    try:
        if system == "Windows":
            _set_autostart_win(enable)
        elif system == "Darwin":  # macOS
            _set_autostart_mac(enable)
    except Exception as e:
        print(f"Ошибка настройки автозапуска: {e}")


def _set_autostart_win(enable: bool):
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)

    if enable:
        # Так как программа пока не скомпилирована в .exe, запускаем через python
        python_path = sys.executable
        script_path = os.path.abspath(sys.argv[0])
        command = f'"{python_path}" "{script_path}"'
        winreg.SetValueEx(key, "SimpleMessenger", 0, winreg.REG_SZ, command)
    else:
        try:
            winreg.DeleteValue(key, "SimpleMessenger")
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)


def _set_autostart_mac(enable: bool):
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.simplemessenger.plist"
    if enable:
        python_path = sys.executable
        script_path = os.path.abspath(sys.argv[0])
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.simplemessenger</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
        with open(plist_path, "w", encoding="utf-8") as f:
            f.write(plist_content)
    else:
        if plist_path.exists():
            os.remove(plist_path)