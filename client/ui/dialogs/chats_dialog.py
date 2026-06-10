import flet as ft
from .base_dialog import BaseDialog


class ChatsDialog(BaseDialog):
    def __init__(self, page: ft.Page, chats_data: list, active_chat_id: int, on_select_chat):
        super().__init__(page)
        self.on_select_chat = on_select_chat

        list_view = ft.ListView(expand=True, spacing=10)

        self.dialog = ft.AlertDialog(
            title=ft.Text("Выберите чат"),
            content=ft.Container(content=list_view, width=300, height=300),
            actions=[ft.TextButton("Закрыть", on_click=lambda e: self.close())]
        )

        for c in chats_data:
            cid, cname, ctype = c['id'], c['name'], c['type']
            icon = ft.Icons.GROUP if ctype == 'global' else ft.Icons.PERSON if ctype == 'dialog' else ft.Icons.BOOKMARK

            list_view.controls.append(
                ft.ListTile(
                    leading=ft.Icon(icon),
                    title=ft.Text(cname),
                    subtitle=ft.Text("Текущий" if cid == active_chat_id else f"Тип: {ctype}"),
                    # cid=cid фиксирует значение переменной для каждой кнопки
                    on_click=lambda e, target_id=cid: self._handle_select(target_id)
                )
            )

    def _handle_select(self, target_id):
        self.close()
        self.on_select_chat(target_id)