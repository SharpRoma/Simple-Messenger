import asyncio
import socket
import sys
import threading
import platform
import logging
import flet as ft
from network import MessengerNetwork
from database import ClientDatabase
from system.crypto import CryptoManager
from system.event_bus import EventBus

logger = logging.getLogger("messenger.app_controller")


class AppController:
    def __init__(self, page: ft.Page, system_adapter, settings_manager):
        self.page = page
        self.os = system_adapter
        self.settings_manager = settings_manager
        self.settings = self.settings_manager.load_settings()

        self.db = None
        self.crypto_mgr = None

        self.current_username = ""
        self.current_password = ""
        self.is_logged_in = False

        # Инициализируем шину событий
        self.event_bus = EventBus()
        self.network = MessengerNetwork(self.event_bus)

        # Подписываемся на события жизненного цикла сети
        self.event_bus.subscribe("disconnect", self.on_net_disconnect)
        self.event_bus.subscribe("reconnect", self.on_net_reconnect)

        self.page.title = "Simple Messenger"
        self.page.window.width = 400
        self.page.window.height = 550
        self.page.window.min_width = 350
        self.page.window.min_height = 400
        self.page.theme_mode = ft.ThemeMode.DARK

        self.page.drawer = ft.NavigationDrawer(controls=[])
        self.page.on_keyboard_event = self.handle_keyboard_event

        # Ленивый импорт для избежания циклических зависимостей
        from ui.controllers.auth_controller import AuthController
        from ui.controllers.chat_controller import ChatController
        
        self.auth = AuthController(self.page, self)
        self.chat = ChatController(self.page, self)

        self.show_login_screen()

        if self.settings.get("auto_login") and self.settings.get("username"):
            self.auto_connect()

    def handle_keyboard_event(self, e: ft.KeyboardEvent):
        if e.key == "Escape" and self.is_logged_in and self.page.drawer:
            async def toggle_drawer():
                if self.page.drawer.open:
                    await self.page.close_drawer()
                else:
                    await self.page.show_drawer()
            self.page.run_task(toggle_drawer)

    def show_login_screen(self):
        self.is_logged_in = False
        self.current_username = ""
        self.db = None
        self.crypto_mgr = None
        
        self.chat.reset_state()
        self.auth.show_login()

    def show_chat_screen(self):
        self.is_logged_in = True
        self.chat.show_chat()

    def auto_connect(self):
        self.auth.handle_login(
            self.settings.get("host"),
            self.settings.get("port"),
            self.settings.get("username"),
            self.settings.get("password"),
            True
        )

    def show_snackbar(self, text: str, color=None):
        snack = ft.SnackBar(ft.Text(text, color=color), duration=2000)
        self.page.overlay.append(snack)
        snack.open = True
        self.page.update()

    async def on_net_disconnect(self, data=None):
        if self.is_logged_in:
            self.page.title = f"Simple Messenger ({self.current_username}) [Offline]"
            self.page.update()

    async def on_net_reconnect(self, data=None):
        if self.is_logged_in:
            self.page.title = f"Simple Messenger ({self.current_username})"
            self.page.update()
