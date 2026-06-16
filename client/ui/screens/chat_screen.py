import flet as ft
from datetime import datetime


class ChatScreen(ft.Container):
    def __init__(
            self,
            current_username: str,
            on_send_message,
            on_attach_file,
            on_open_drawer,
            on_toggle_pin,
            on_copy_message,
            on_delete_message,
            on_download_file,
            on_input_focus,
            on_add_member
    ):
        super().__init__()
        self.expand = True
        self.current_username = current_username

        self.on_send_message = on_send_message
        self.on_attach_file = on_attach_file
        self.on_open_drawer = on_open_drawer
        self.on_toggle_pin = on_toggle_pin
        self.on_copy_message = on_copy_message
        self.on_delete_message = on_delete_message
        self.on_download_file = on_download_file
        self.on_input_focus = on_input_focus

        self.is_pinned = False
        self._build_ui()

    def _build_ui(self):
        self.chat_history = ft.ListView(expand=True, spacing=5, auto_scroll=True)
        self.msg_input = ft.TextField(
            hint_text="Написать сообщение...", expand=True,
            on_submit=self._submit_message, on_focus=lambda e: self.on_input_focus()
        )

        # --- НОВЫЙ ДИЗАЙН ВЕРХНЕЙ ПАНЕЛИ ---
        self.chat_title = ft.Text("Simple Messenger", size=18, weight="bold", expand=True,
                                  text_align=ft.TextAlign.CENTER)
        self.pin_btn = ft.IconButton(
            icon=ft.Icons.PUSH_PIN, icon_color=ft.Colors.WHITE54, tooltip="Поверх всех", on_click=self._toggle_pin
        )

        self.add_user_btn = ft.IconButton(icon=ft.Icons.PERSON_ADD, tooltip="Добавить участника",
                                          on_click=lambda e: self.on_add_member(), visible=False)

        header_row = ft.Row([
            ft.IconButton(icon=ft.Icons.MENU, on_click=lambda e: self.on_open_drawer()),
            self.chat_title,
            ft.Row([self.add_user_btn, self.pin_btn])  # <--- Теперь тут 2 кнопки справа
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        header_row = ft.Row([
            ft.IconButton(icon=ft.Icons.MENU, on_click=lambda e: self.on_open_drawer()),  # Бургер слева
            self.chat_title,  # Название по центру
            self.pin_btn  # Заколка справа
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        input_row = ft.Row([
            ft.IconButton(icon=ft.Icons.ATTACH_FILE, icon_color=ft.Colors.GREY_400,
                          on_click=lambda e: self.on_attach_file()),
            self.msg_input,
            ft.IconButton(icon=ft.Icons.SEND, icon_color=ft.Colors.BLUE, on_click=self._submit_message)
        ])

        self.content = ft.Column([
            header_row,
            ft.Divider(height=1),
            ft.Container(content=self.chat_history, expand=True, border_radius=5, padding=10, bgcolor="#1e1e1e"),
            input_row
        ], expand=True)

    def set_chat_title(self, title: str, is_group: bool = False):
        self.chat_title.value = title
        self.add_user_btn.visible = is_group  # Показывать кнопку только для групп!
        self.chat_title.update()
        self.add_user_btn.update()

    # --- Внутренняя логика UI ---
    def _submit_message(self, e):
        text = self.msg_input.value.strip()
        if text:
            self.msg_input.value = ""
            self.msg_input.update()
            # Передаем текст наверх, контроллер сам решит, это команда /chats или обычный текст
            self.on_send_message(text)

    def _toggle_pin(self, e):
        self.is_pinned = not self.is_pinned
        self.pin_btn.icon_color = ft.Colors.RED if self.is_pinned else ft.Colors.WHITE54
        self.pin_btn.update()
        self.on_toggle_pin(self.is_pinned)

    # --- Публичные методы (API для управления чатом снаружи) ---
    def clear_messages(self):
        self.chat_history.controls.clear()
        self.chat_history.update()

    def add_system_message(self, text: str, color=ft.Colors.WHITE):
        """Для системных уведомлений типа '--- Вы в чате ---' или '[🔔] Новое сообщение'"""
        row = ft.Row([ft.Text(text, color=color, font_family="Consolas", expand=True)])
        self.chat_history.controls.append(row)
        self.chat_history.update()

    def add_message(self, sender: str, text: str, timestamp: float, msg_id: int = None, file_name: str = None):
        """Добавление сообщения от пользователя (текст или файл)"""
        ts = datetime.fromtimestamp(timestamp).strftime('%H:%M')
        is_own = (sender == self.current_username)
        actions = []

        if file_name:
            # Отрисовка файла
            content = ft.Text(f"[{ts}] {sender}: 📎 Файл: {file_name}", color=ft.Colors.BLUE_200, italic=True,
                              expand=True)
            # Обрати внимание на m=msg_id, f=file_name — это защищает лямбду от замыкания!
            actions.append(ft.IconButton(
                icon=ft.Icons.DOWNLOAD, icon_size=16, tooltip="Скачать",
                on_click=lambda e, m=msg_id, f=file_name: self.on_download_file(m, f)
            ))
        else:
            # Отрисовка текста
            msg_text = f"[{ts}] {sender}: {text}"
            content = ft.Text(msg_text, font_family="Consolas", selectable=True, expand=True)
            actions.append(ft.IconButton(
                icon=ft.Icons.COPY, icon_size=16, icon_color=ft.Colors.GREY_600, tooltip="Копировать",
                on_click=lambda e, t=text: self.on_copy_message(t)
            ))

        if is_own and msg_id:
            actions.append(ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE, icon_size=16, icon_color=ft.Colors.RED_400, tooltip="Удалить",
                on_click=lambda e, m=msg_id: self.on_delete_message(m)
            ))

        row = ft.Row(
            controls=[content] + actions,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            key=f"msg_{msg_id}" if msg_id else None
        )
        self.chat_history.controls.append(row)
        self.chat_history.update()

    def remove_message(self, msg_id: int):
        """Мгновенное удаление сообщения из UI по ID"""
        target_key = f"msg_{msg_id}"
        for ctrl in self.chat_history.controls:
            if getattr(ctrl, "key", None) == target_key:
                self.chat_history.controls.remove(ctrl)
                self.chat_history.update()
                break