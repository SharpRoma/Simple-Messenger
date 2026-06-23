import flet as ft
from .base_dialog import BaseDialog

class AddMemberDialog(BaseDialog):
    def __init__(self, page: ft.Page, on_add, on_search_users):
        super().__init__(page)
        self.on_search_users = on_search_users

        self.user_input = ft.TextField(
            label="Логин пользователя",
            autofocus=True,
            on_change=self._handle_search_change
        )
        self.results_list = ft.ListView(expand=True, spacing=5, height=120)

        self.content_container = ft.Column([
            self.user_input,
            self.results_list
        ], spacing=10, height=200, width=300)

        self.dialog = ft.AlertDialog(
            title=ft.Text("Добавить участника"),
            content=self.content_container,
            actions=[
                ft.TextButton("Добавить", on_click=lambda e: self._submit(on_add)),
                ft.TextButton("Отмена", on_click=lambda e: self.close())
            ]
        )

    async def _handle_search_change(self, e):
        query = self.user_input.value.strip()
        if not query:
            self.results_list.controls.clear()
            try:
                self.results_list.update()
            except Exception:
                pass
            return

        users = await self.on_search_users(query)
        self.results_list.controls.clear()
        for user in users:
            self.results_list.controls.append(
                ft.ListTile(
                    title=ft.Text(user),
                    leading=ft.Icon(ft.Icons.PERSON, size=18),
                    on_click=lambda e, u=user: self._select_user(u)
                )
            )
        try:
            self.results_list.update()
        except Exception:
            pass

    def _select_user(self, username):
        self.user_input.value = username
        self.user_input.update()
        self.results_list.controls.clear()
        try:
            self.results_list.update()
        except Exception:
            pass

    def _submit(self, callback):
        if self.user_input.value.strip():
            self.close()
            callback(self.user_input.value.strip())