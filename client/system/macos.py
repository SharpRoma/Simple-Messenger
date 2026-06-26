import subprocess
import flet as ft
import logging
from .base import SystemAdapter

logger = logging.getLogger("messenger.system.macos")

class MacOSAdapter(SystemAdapter):
    def notify(self, title: str, text: str):
        try:
            # БЕЗОПАСНЫЙ ВЫЗОВ: Защита от AppleScript-инъекций.
            # Мы не встраиваем текст в сам скрипт, а передаем его как аргументы командной строки.
            apple_script = """
            on run argv
                display notification (item 1 of argv) with title "Simple Messenger" subtitle (item 2 of argv)
            end run
            """

            subprocess.run([
                "osascript",
                "-e", apple_script,
                "--", text, title
            ])
        except Exception as e:
            logger.error(f"Mac Notification Error: {e}")

    def set_tray_badge(self, count_str: str = None):
        if count_str is False or count_str == "0":
            count_str = None
        try:
            self.page.window.badge_label = count_str
            self.page.update()
        except Exception as e:
            logger.error(f"Failed to set Dock badge: {e}")

    def handle_window_event(self, event_name: str):
        if event_name == "close":
            # На маке по крестику приложение не закрывается, а сворачивается
            self.page.window.minimized = True
            self.page.update()
        elif event_name in ["focus", "restore"]:
            self.set_tray_badge(None)