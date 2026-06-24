import pytest
from unittest.mock import MagicMock, patch
import flet as ft
from ui.controllers.app_controller import AppController


class MockWindow:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.min_width = 0
        self.min_height = 0


class MockPage:
    def __init__(self):
        self.title = ""
        self.window = MockWindow()
        self.theme_mode = None
        self.drawer = None
        self.on_keyboard_event = None
        self.overlay = []

    def update(self):
        pass

    def run_task(self, task):
        pass


def test_app_controller_init():
    page = MockPage()
    system_adapter = MagicMock()
    settings_manager = MagicMock()
    settings_manager.load_settings.return_value = {
        "auto_login": False,
        "username": "testuser",
        "host": "localhost",
        "port": 8000
    }

    # Мокаем вложенные контроллеры во время инициализации AppController
    with patch("ui.controllers.auth_controller.AuthController") as MockAuth, \
         patch("ui.controllers.chat_controller.ChatController") as MockChat:
        
        controller = AppController(page, system_adapter, settings_manager)
        
        assert controller.page == page
        assert controller.os == system_adapter
        assert controller.settings_manager == settings_manager
        assert controller.settings["username"] == "testuser"
        assert controller.is_logged_in is False
        assert page.title == "Simple Messenger"
        assert page.window.width == 400
        assert page.window.height == 550
        assert page.theme_mode == ft.ThemeMode.DARK
        
        MockAuth.assert_called_once()
        MockChat.assert_called_once()
