import flet as ft
from .base_dialog import BaseDialog

class CreateGroupDialog(BaseDialog):
    def __init__(self, page: ft.Page, on_create):
        super().__init__(page)
        self.name_input = ft.TextField(label="Название группы", autofocus=True)
        self.dialog = ft.AlertDialog(
            title=ft.Text("Новая группа"), content=self.name_input,
            actions=[
                ft.TextButton("Создать", on_click=lambda e: self._submit(on_create)),
                ft.TextButton("Отмена", on_click=lambda e: self.close())
            ]
        )
    def _submit(self, callback):
        if self.name_input.value.strip():
            self.close()
            callback(self.name_input.value.strip())