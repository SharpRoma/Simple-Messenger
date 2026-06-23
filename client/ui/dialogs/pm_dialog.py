import flet as ft
from .base_dialog import BaseDialog

class PmDialog(BaseDialog):
    def __init__(self, page: ft.Page, on_create_pm, on_search_users):
        super().__init__(page)
        self.on_create_pm = on_create_pm
        self.on_search_users = on_search_users

        self.pm_input = ft.TextField(
            label="Логин пользователя",
            autofocus=True,
            on_submit=self._handle_submit,
            on_change=self._handle_search_change
        )

        self.results_list = ft.ListView(expand=True, spacing=5, height=120)

        # Компонуем в колонку фиксированной высоты, чтобы результаты вмещались
        self.content_container = ft.Column([
            self.pm_input,
            self.results_list
        ], spacing=10, height=200, width=300)

        self.dialog = ft.AlertDialog(
            title=ft.Text("Новый диалог"),
            content=self.content_container,
            actions=[
                ft.TextButton("Создать", on_click=self._handle_submit),
                ft.TextButton("Отмена", on_click=lambda e: self.close())
            ]
        )

    async def _handle_search_change(self, e):
        query = self.pm_input.value.strip()
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
        self.pm_input.value = username
        self.pm_input.update()
        self.results_list.controls.clear()
        try:
            self.results_list.update()
        except Exception:
            pass

    def _handle_submit(self, e):
        target = self.pm_input.value.strip()
        if target:
            self.close()
            # Передаем логин наверх в контроллер
            self.on_create_pm(target)