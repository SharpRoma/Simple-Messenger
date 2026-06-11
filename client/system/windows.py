import threading
import os
import pystray
from PIL import Image
import flet as ft
from .base import SystemAdapter


class WindowsAdapter(SystemAdapter):
    def __init__(self, page: ft.Page, icon_path: str, unread_icon_path: str, ico_path: str):
        super().__init__(page)
        self.icon_path = icon_path
        self.unread_icon_path = unread_icon_path
        self.ico_path = ico_path
        self.tray_icon = None

    def setup_tray(self):
        # Запускаем трей в отдельном потоке, чтобы он не блокировал Flet
        threading.Thread(target=self._run_tray, daemon=True).start()

    def _run_tray(self):
        from pystray import MenuItem as item
        menu = pystray.Menu(
            item('Развернуть', self._restore_window, default=True),
            item('Выход', self._quit_app)
        )
        self.tray_icon = pystray.Icon(
            "SimpleMessenger",
            Image.open(self.icon_path),
            "Simple Messenger",
            menu
        )
        self.tray_icon.run()

    def _restore_window(self, icon, item_):
        # Трей работает в фоне. Передаем задачу разворачивания в движок Flet!
        async def restore_task():
            self.set_tray_badge(False)

            # Возвращаем окну видимость и убираем статус свернутого
            self.page.window.visible = True
            self.page.window.minimized = False
            self.page.window.focused = True

            # ТРЮК ДЛЯ WINDOWS: Дергаем окно "поверх всех", чтобы ОС точно его показала
            was_pinned = getattr(self.page.window, "always_on_top", False)
            self.page.window.always_on_top = True
            self.page.update()

            # И сразу возвращаем статус-кво (если пользователь не закреплял его заколкой)
            if not was_pinned:
                self.page.window.always_on_top = False
                self.page.update()

        # Заставляем страницу Flet выполнить это в своем потоке
        self.page.run_task(restore_task)

    def _quit_app(self, icon, item_):
        # 1. Убираем иконку из трея
        self.tray_icon.stop()

        # 2. Мягко просим Flet закрыть окно (нативно)
        async def exit_task():
            # Отключаем защиту от закрытия
            self.page.window.prevent_close = False
            # Говорим интерфейсу штатно закрыться
            self.page.window.close()

        self.page.run_task(exit_task)

        self.page.run_task(exit_task)

    def notify(self, title: str, text: str):
        try:
            if self.tray_icon:
                # Встроенные нативные уведомления pystray (без plyer!)
                self.tray_icon.notify(text, title=title)
        except Exception as e:
            print(f"Win Notification Error: {e}")

    def set_tray_badge(self, has_unread: bool):
        if self.tray_icon:
            try:
                icon_file = self.unread_icon_path if has_unread else self.icon_path
                self.tray_icon.icon = Image.open(icon_file)
            except:
                pass

    def handle_window_event(self, event_name: str):
        if event_name == "close":
            # На Windows по крестику прячем в трей
            self.page.window.visible = False
            self.page.update()
        elif event_name in ["focus", "restore"]:
            self.set_tray_badge(False)