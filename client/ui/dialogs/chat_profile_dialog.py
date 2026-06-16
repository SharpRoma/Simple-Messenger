import flet as ft
from datetime import datetime
from .base_dialog import BaseDialog


class ChatProfileDialog(BaseDialog):
    def __init__(self, page: ft.Page, chat_name: str, members: list, on_add_click):
        super().__init__(page)

        # Список участников
        members_list = ft.ListView(spacing=10, height=250)

        for m in members:
            # Логика отображения статусов
            if m.get('is_online'):
                status_text = "в сети"
                status_color = ft.Colors.GREEN
            elif m.get('last_seen'):
                ts = datetime.fromtimestamp(m['last_seen']).strftime('%d.%m %H:%M')
                status_text = f"был(а) {ts}"
                status_color = ft.Colors.GREY_500
            else:
                status_text = "оффлайн"
                status_color = ft.Colors.GREY_500

            members_list.controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.PERSON),
                    title=ft.Text(m['username']),
                    subtitle=ft.Text(status_text, color=status_color)
                )
            )

        # Собираем окно
        self.dialog = ft.AlertDialog(
            title=ft.Text(f"Профиль: {chat_name}", weight="bold"),
            content=ft.Column([
                ft.Text("Участники:", weight="bold"),
                members_list
            ], tight=True, width=300),
            actions=[
                ft.TextButton("Добавить участника", icon=ft.Icons.PERSON_ADD,
                              on_click=lambda e: self._handle_add(on_add_click)),
                ft.TextButton("Закрыть", on_click=lambda e: self.close())
            ]
        )

    def _handle_add(self, callback):
        self.close()
        callback()  # Открывает следующее окно ввода логина