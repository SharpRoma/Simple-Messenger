import subprocess
import flet as ft
from .base import SystemAdapter

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
            print(f"Mac Notification Error: {e}")

    def set_tray_badge(self, has_unread: bool):
        # На MacOS badge для Flet пока реализован слабо,
        # но мы оставляем метод пустым, чтобы приложение не падало
        pass

    def handle_window_event(self, event_name: str):
        if event_name == "close":
            # На маке по крестику приложение не закрывается, а сворачивается
            self.page.window.minimized = True
            self.page.update()
        elif event_name in ["focus", "restore"]:
            self.set_tray_badge(False)