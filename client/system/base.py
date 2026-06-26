import flet as ft

class SystemAdapter:
    def __init__(self, page: ft.Page):
        self.page = page

    def notify(self, title: str, text: str):
        raise NotImplementedError

    def set_tray_badge(self, count_str: str = None):
        raise NotImplementedError

    def handle_window_event(self, event_name: str):
        raise NotImplementedError

    def setup_tray(self):
        """Инициализация трея (если поддерживается ОС)"""
        pass

    def restore_window(self):
        """Восстановление видимости окна и вывод его на передний план"""
        async def restore_task():
            try:
                self.set_tray_badge(False)
            except Exception:
                pass
            
            self.page.window.visible = True
            self.page.window.minimized = False
            self.page.window.focused = True

            # Трюк с always_on_top для вывода окна поверх других
            was_pinned = getattr(self.page.window, "always_on_top", False)
            self.page.window.always_on_top = True
            self.page.update()

            if not was_pinned:
                self.page.window.always_on_top = False
                self.page.update()

        self.page.run_task(restore_task)