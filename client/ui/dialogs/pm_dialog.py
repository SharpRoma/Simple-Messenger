import flet as ft
from .base_dialog import BaseDialog

class PmDialog(BaseDialog):
    def __init__(self, page: ft.Page, on_create_pm):
        super().__init__(page)
        self.on_create_pm = on_create_pm

        self.pm_input = ft.TextField(
            label="Логин пользователя",
            autofocus=True,
            on_submit=self._handle_submit
        )

        self.dialog = ft.AlertDialog(
            title=ft.Text("Новый диалог"),
            content=self.pm_input,
            actions=[
                ft.TextButton("Создать", on_click=self._handle_submit),
                ft.TextButton("Отмена", on_click=lambda e: self.close())
            ]
        )

    def _handle_submit(self, e):
        target = self.pm_input.value.strip()
        if target:
            self.close()
            # Передаем логин наверх в контроллер
            self.on_create_pm(target)