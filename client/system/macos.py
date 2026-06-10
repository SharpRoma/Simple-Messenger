import subprocess
import flet as ft
from .base import SystemAdapter

class MacOSAdapter(SystemAdapter):
    def notify(self, title: str, text: str):
        try:
            # Экранируем кавычки для безопасности
            safe_text = text.replace('"', '\\"').replace("'", "\\'")
            safe_title = title.replace('"', '\\"').replace("'", "\\'")
            subprocess.run([
                "osascript", "-e",
                f'display notification "{safe_text}" with title "Simple Messenger" subtitle "{safe_title}"'
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