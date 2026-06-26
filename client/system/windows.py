import threading
import os
import pystray
from PIL import Image
import flet as ft
import logging
from .base import SystemAdapter

logger = logging.getLogger("messenger.system.windows")


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
        self.restore_window()

    def _quit_app(self, icon, item_):
        # 1. Убираем иконку из трея
        self.tray_icon.stop()

        # 2. Мягко и нативно завершаем Flet
        async def exit_task():
            import asyncio

            # Отключаем наш перехватчик крестика, чтобы окно реально закрылось, а не спряталось
            self.page.window.on_event = None

            # Снимаем блокировку закрытия
            self.page.window.prevent_close = False
            self.page.update()

            # Даем Flet 0.1 сек на применение настроек
            await asyncio.sleep(0.1)

            # Нативно просим окно закрыться.
            # Flet сам всё потушит и чисто завершит Python-процесс
            await self.page.window.close()

        self.page.run_task(exit_task)

    def notify(self, title: str, text: str):
        try:
            if self.tray_icon:
                # Встроенные нативные уведомления pystray (без plyer!)
                self.tray_icon.notify(text, title=title)
        except Exception as e:
            logger.error(f"Win Notification Error: {e}")

    def set_tray_badge(self, count_str: str = None):
        if count_str is False or count_str == "0":
            count_str = None

        if self.tray_icon:
            try:
                has_unread = bool(count_str)
                icon_file = self.unread_icon_path if has_unread else self.icon_path
                self.tray_icon.icon = Image.open(icon_file)
            except Exception as e:
                logger.error(f"Failed to set tray icon: {e}")

        try:
            self.page.window.badge_label = count_str
            self.page.update()
        except Exception as e:
            logger.error(f"Failed to set taskbar badge: {e}")

    def handle_window_event(self, event_name: str):
        if event_name == "close":
            # На Windows по крестику прячем в трей
            self.page.window.visible = False
            self.page.update()
        elif event_name in ["focus", "restore"]:
            self.set_tray_badge(None)