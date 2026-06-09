import flet as ft
import asyncio
import json
from datetime import datetime


class MessengerClient:
    def __init__(self, page: ft.Page):
        self.page = page
        self.reader = None
        self.writer = None
        self.active_chat_id = 1

        self.page.title = "Simple Messenger"
        self.page.window.width = 400
        self.page.window.height = 550
        self.page.window.min_width = 350
        self.page.window.min_height = 400
        self.page.theme_mode = ft.ThemeMode.DARK
        self.btn_class = getattr(ft, 'Button', ft.ElevatedButton)

        self.show_login_screen()

    # --- ЖЕЛЕЗОБЕТОННЫЕ МОДАЛЬНЫЕ ОКНА ---

    def show_pm_modal(self):
        """Окно для создания новой лички"""
        pm_input = ft.TextField(label="Логин пользователя", autofocus=True)

        async def on_submit(e):
            target = pm_input.value.strip()
            dlg.open = False
            self.page.update()
            if target:
                await self._send_json({"action": "create_dialog", "target": target})

        def on_cancel(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Новый диалог"),
            content=pm_input,
            actions=[
                ft.TextButton("Создать", on_click=on_submit),
                ft.TextButton("Отмена", on_click=on_cancel)
            ]
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def show_chats_modal(self, chats_data):
        """Окно со списком чатов"""
        list_view = ft.ListView(expand=True, spacing=10)

        dlg = ft.AlertDialog(
            title=ft.Text("Выберите чат"),
            content=ft.Container(content=list_view, width=300, height=300),
        )

        def close_dlg(e):
            dlg.open = False
            self.page.update()

        dlg.actions = [ft.TextButton("Закрыть", on_click=close_dlg)]

        for c in chats_data:
            cid, cname, ctype = c['id'], c['name'], c['type']
            icon = ft.Icons.GROUP if ctype == 'global' else ft.Icons.PERSON if ctype == 'dialog' else ft.Icons.BOOKMARK

            def make_click_handler(chat_id):
                async def handler(e):
                    dlg.open = False
                    self.page.update()
                    self.active_chat_id = chat_id
                    await self._send_json({"action": "get_history", "chat_id": chat_id, "limit": 20})

                return handler

            list_view.controls.append(
                ft.ListTile(
                    leading=ft.Icon(icon),
                    title=ft.Text(cname),
                    subtitle=ft.Text("Текущий" if cid == self.active_chat_id else f"Тип: {ctype}"),
                    on_click=make_click_handler(cid)
                )
            )

        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # --- ЭКРАНЫ ---

    async def focus_user_input(self, e):
        await self.user_input.focus()

    async def focus_pass_input(self, e):
        await self.pass_input.focus()

    # --- ЭКРАНЫ ---
    def show_login_screen(self):
        self.page.clean()
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER

        # Теперь мы вызываем асинхронные методы вместо lambda
        self.host_input = ft.TextField(
            label="IP сервера",
            value="127.0.0.1",
            width=300,
            on_submit=self.focus_user_input
        )
        self.user_input = ft.TextField(
            label="Логин",
            width=300,
            on_submit=self.focus_pass_input
        )
        self.pass_input = ft.TextField(
            label="Пароль",
            password=True,
            width=300,
            on_submit=self.connect_to_server
        )
        self.login_err = ft.Text(color="red")

        self.page.add(
            ft.Text("Вход в Messenger", size=24, weight="bold"),
            self.host_input,
            self.user_input,
            self.pass_input,
            self.login_err,
            self.btn_class("Подключиться", on_click=self.connect_to_server)
        )

    def show_chat_screen(self):
        self.page.clean()
        self.page.horizontal_alignment = ft.CrossAxisAlignment.START
        self.page.vertical_alignment = ft.MainAxisAlignment.START

        self.chat_history = ft.ListView(expand=True, spacing=5, auto_scroll=True)
        self.msg_input = ft.TextField(
            hint_text="Написать сообщение...",
            expand=True,
            on_submit=self.send_message_ui
        )

        buttons_row = ft.Row(
            [
                self.btn_class("Чаты", icon=ft.Icons.LIST, on_click=self.btn_click_chats),
                self.btn_class("Личка", icon=ft.Icons.PERSON_ADD, on_click=self.btn_click_pm),
                self.btn_class("Обновить", icon=ft.Icons.REFRESH, on_click=self.btn_click_history),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )

        main_layout = ft.Column(
            [
                buttons_row,
                ft.Divider(),
                ft.Container(
                    content=self.chat_history,
                    expand=True,
                    border_radius=5,
                    padding=10,
                    bgcolor="#1e1e1e"
                ),
                ft.Row(
                    [
                        self.msg_input,
                        ft.IconButton(icon=ft.Icons.SEND, icon_color=ft.Colors.BLUE, on_click=self.send_message_ui)
                    ]
                )
            ],
            expand=True
        )

        self.page.add(main_layout)
        self.page.update()

    def print_to_console(self, text, color=ft.Colors.WHITE):
        try:
            self.chat_history.controls.append(
                ft.Text(text, color=color, font_family="Consolas", selectable=True)
            )
            self.chat_history.update()
        except:
            pass

    async def connect_to_server(self, e):
        host = self.host_input.value
        username = self.user_input.value
        password = self.pass_input.value
        self.login_err.value = "Подключение..."
        self.page.update()

        try:
            self.reader, self.writer = await asyncio.open_connection(host, 8888)

            auth_data = {"username": username, "password": password}
            self.writer.write(json.dumps(auth_data).encode() + b'\n')
            await self.writer.drain()

            response_line = await self.reader.readline()
            response = json.loads(response_line.decode().strip())

            if response.get("status") != "ok":
                self.login_err.value = f"Ошибка: {response.get('msg')}"
                self.page.update()
                return

            self.show_chat_screen()
            await self._send_json({"action": "get_history", "chat_id": 1, "limit": 20, "offset": 0})
            asyncio.create_task(self.receive_loop())

        except Exception as ex:
            self.login_err.value = f"Ошибка: {ex}"
            self.page.update()

    async def receive_loop(self):
        try:
            while True:
                line = await self.reader.readline()
                if not line:
                    self.print_to_console("❌ Соединение с сервером разорвано.", ft.Colors.RED)
                    break

                data = json.loads(line.decode().strip())
                action = data.get("action")

                if action == "new_msg":
                    chat_id = data.get("chat_id")
                    msg = data.get("message")
                    ts = datetime.fromtimestamp(msg.get("timestamp")).strftime('%H:%M')

                    if chat_id == self.active_chat_id:
                        self.print_to_console(f"[{ts}] {msg['sender']}: {msg['text']}")
                    else:
                        self.print_to_console(f"[🔔] Новое сообщение в чате ID:{chat_id}", ft.Colors.YELLOW)

                elif action == "history":
                    self.chat_history.controls.clear()
                    messages = data.get("messages", [])
                    chat_id = data.get("chat_id")

                    self.print_to_console(f"--- Вы в чате ID: {chat_id} ---", ft.Colors.BLUE_200)
                    for msg in messages:
                        ts = datetime.fromtimestamp(msg.get("timestamp")).strftime('%H:%M')
                        self.print_to_console(f"[{ts}] {msg['sender']}: {msg['text']}")

                elif action == "chat_list":
                    # Вызываем отрисовку модального окна со списком!
                    self.show_chats_modal(data.get("chats", []))

                elif action == "dialog_created":
                    new_id = data.get("chat_id")
                    target = data.get("target")
                    self.print_to_console(f"✅ Создан диалог с {target}. Переключаемся...", ft.Colors.GREEN)

                    self.active_chat_id = new_id
                    await self._send_json({"action": "get_history", "chat_id": new_id, "limit": 20})

        except Exception as e:
            pass

    async def btn_click_chats(self, e):
        await self._send_json({"action": "get_chats"})

    async def btn_click_pm(self, e):
        self.show_pm_modal()

    async def btn_click_history(self, e):
        await self._send_json({"action": "get_history", "chat_id": self.active_chat_id, "limit": 20})

    async def send_message_ui(self, e):
        text = self.msg_input.value.strip()
        if not text or not self.writer:
            return

        self.msg_input.value = ""
        self.page.update()

        if text.startswith('/'):
            parts = text.split()
            cmd = parts[0].lower()
            if cmd == '/chats':
                await self._send_json({"action": "get_chats"})
            elif cmd == '/pm' and len(parts) > 1:
                await self._send_json({"action": "create_dialog", "target": parts[1]})
        else:
            await self._send_json({"action": "send_msg", "chat_id": self.active_chat_id, "text": text})

    async def _send_json(self, data):
        if self.writer:
            self.writer.write(json.dumps(data).encode() + b'\n')
            await self.writer.drain()


def main(page: ft.Page):
    app = MessengerClient(page)


if __name__ == "__main__":
    if hasattr(ft, 'run'):
        ft.run(main)
    else:
        ft.app(main)