import flet as ft
from ui.controllers.app_controller import AppController


class MainWindow:
    """Тонкий фасад (Shell) для обратной совместимости с main.py.
    Вся бизнес-логика и управление UI делегированы AppController.
    """
    def __init__(self, page: ft.Page, system_adapter, settings_manager):
        self.controller = AppController(page, system_adapter, settings_manager)