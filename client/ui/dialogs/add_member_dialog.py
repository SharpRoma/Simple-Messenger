import flet as ft
from .base_dialog import BaseDialog

class AddMemberDialog(BaseDialog):
    def __init__(self, page: ft.Page, on_add):
        super().__init__(page)
        self.user_input = ft.TextField(label="Логин пользователя", autofocus=True)
        self.dialog = ft.AlertDialog(
            title=ft.Text("Добавить участника"), content=self.user_input,
            actions=[
                ft.TextButton("Добавить", on_click=lambda e: self._submit(on_add)),
                ft.TextButton("Отмена", on_click=lambda e: self.close())
            ]
        )
    def _submit(self, callback):
        if self.user_input.value.strip():
            self.close()
            callback(self.user_input.value.strip())