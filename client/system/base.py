import flet as ft

class SystemAdapter:
    def __init__(self, page: ft.Page):
        self.page = page

    def notify(self, title: str, text: str):
        raise NotImplementedError

    def set_tray_badge(self, has_unread: bool):
        raise NotImplementedError

    def handle_window_event(self, event_name: str):
        raise NotImplementedError

    def setup_tray(self):
        """Инициализация трея (если поддерживается ОС)"""
        pass