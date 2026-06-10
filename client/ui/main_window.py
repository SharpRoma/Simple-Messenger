import flet as ft
import asyncio
import base64
from network import MessengerNetwork
from ui.screens.login_screen import LoginScreen
from ui.screens.chat_screen import ChatScreen
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.pm_dialog import PmDialog
from ui.dialogs.register_dialog import RegisterDialog


class MainWindow:
    def __init__(self, page: ft.Page, system_adapter, settings_manager):
        self.page = page
        self.os = system_adapter
        self.settings_manager = settings_manager
        self.settings = self.settings_manager.load_settings()

        self.current_username = ""
        self.active_chat_id = 1
        self.chats_info = {}
        self.pending_downloads = {}

        self.network = MessengerNetwork(self.on_net_message, self.on_net_disconnect)

        self.page.title = "Simple Messenger"
        self.page.window.width = 400
        self.page.window.height = 550
        self.page.window.min_width = 350
        self.page.window.min_height = 400
        self.page.theme_mode = ft.ThemeMode.DARK

        self.page.drawer = ft.NavigationDrawer(controls=[])

        self.show_login_screen()

        if self.settings.get("auto_login") and self.settings.get("username"):
            self.auto_connect()

    def get_chat_name(self, chat_data: dict) -> str:
        """Форматирует имя чата для отображения, даже если в логинах есть спецсимволы"""
        name = chat_data.get('name', 'Неизвестный чат')

        if chat_data.get('type') == 'dialog':
            # Чат может называться "мойЛогин_чужойЛогин" или "чужойЛогин_мойЛогин"
            prefix = f"{self.current_username}_"
            suffix = f"_{self.current_username}"

            if name.startswith(prefix):
                return name[len(prefix):]  # Отрезаем спереди
            elif name.endswith(suffix):
                return name[:-len(suffix)]  # Отрезаем сзади

        return name

    def show_login_screen(self):
        self.page.clean()
        self.page.drawer = None
        self.is_logged_in = False
        self.login_screen = LoginScreen(
            settings=self.settings,
            on_login_callback=self.handle_login,
            on_show_register_callback=self.show_register_modal
        )
        self.page.add(self.login_screen)

    def show_chat_screen(self):
        self.page.clean()

        def open_menu():
            async def open_task():
                if self.page.drawer:
                    # УБРАЛИ АРГУМЕНТ ИЗ СКОБОК!
                    await self.page.show_drawer()

            self.page.run_task(open_task)

        self.chat_screen = ChatScreen(
            current_username=self.current_username,
            on_send_message=self.handle_send_message,
            on_attach_file=self.handle_attach_file,
            on_open_drawer=open_menu,
            on_toggle_pin=self.handle_toggle_pin,
            on_copy_message=self.handle_copy_message,
            on_delete_message=self.handle_delete_message,
            on_download_file=self.handle_download_file,
            on_input_focus=lambda: self.os.set_tray_badge(False)
        )
        self.page.add(self.chat_screen)

    def handle_login(self, host, username, password, auto_login):
        async def login_task():
            response = await self.network.connect(host, 8888, username, password)

            if response.get("status") != "ok":
                self.login_screen.show_error(f"Ошибка: {response.get('msg')}")
                return

            self.current_username = username
            self.settings.update({
                "host": host,
                "username": username,
                "password": password if auto_login else "",
                "auto_login": auto_login
            })
            self.settings_manager.save_settings(self.settings)

            self.page.title = f"Simple Messenger ({self.current_username})"

            self.show_chat_screen()
            await self.network.send({"action": "get_chats"})
            await self.network.send({"action": "get_history", "chat_id": 1, "limit": 20, "offset": 0})

            self.page.run_task(self.network.listen)

        self.page.run_task(login_task)

    def auto_connect(self):
        self.handle_login(
            self.settings.get("host"),
            self.settings.get("username"),
            self.settings.get("password"),
            True
        )

    def handle_send_message(self, text: str):
        async def send_task():
            if text.startswith('/'):
                parts = text.split()
                cmd = parts[0].lower()
                if cmd == '/chats':
                    self.page.run_task(self.network.send, {"action": "get_chats"})
                elif cmd == '/pm' and len(parts) > 1:
                    await self.network.send({"action": "create_dialog", "target": parts[1]})
            else:
                await self.network.send({"action": "send_msg", "chat_id": self.active_chat_id, "text": text})

        self.page.run_task(send_task)

    def handle_toggle_pin(self, is_pinned: bool):
        self.page.window.always_on_top = is_pinned
        self.page.update()

    def handle_copy_message(self, text: str):
        async def copy_task():
            await self.page.set_clipboard_async(text)
            self.show_snackbar("Скопировано!")

        self.page.run_task(copy_task)

    def show_snackbar(self, text: str):
        snack = ft.SnackBar(ft.Text(text), duration=2000)
        self.page.overlay.append(snack)
        snack.open = True
        self.page.update()

    def show_register_modal(self):
        current_host = self.login_screen.host_input.value.strip()

        async def on_register(host, username, password, secret):
            response = await self.network.connect(host, 8888, username, password, mode="register", secret=secret)
            if response.get("status") != "ok":
                return False, response.get('msg', 'Неизвестная ошибка')

            self.login_screen.host_input.value = host
            self.login_screen.user_input.value = username
            self.login_screen.pass_input.value = password
            self.page.update()

            self.handle_login(host, username, password, self.login_screen.auto_login_checkbox.value)
            return True, ""

        dialog = RegisterDialog(self.page, current_host, on_register)
        dialog.show()

    def show_pm_modal(self):
        def on_create_pm(target_username):
            self.page.run_task(self.network.send, {"action": "create_dialog", "target": target_username})

        dialog = PmDialog(self.page, on_create_pm)
        dialog.show()

    def show_settings_modal(self):
        def on_settings_changed(new_settings):
            self.settings = new_settings
            self.settings_manager.save_settings(self.settings)
            self.os.set_autostart(self.settings.get("auto_start", False))

        def on_logout():
            self.settings["auto_login"] = False
            self.settings["password"] = ""
            self.settings_manager.save_settings(self.settings)

            # Сначала красиво закрываем меню, потом отключаемся
            async def close_and_exit():
                if self.page.drawer:
                    await self.page.close_drawer()
                await self.network.disconnect()

            self.page.run_task(close_and_exit)
            self.show_login_screen()

        dialog = SettingsDialog(self.page, self.settings, on_settings_changed, on_logout)
        dialog.show()

    # ==========================================
    #       РАБОТА С ФАЙЛАМИ (FLET 1.0+ API)
    # ==========================================
    def handle_attach_file(self):
        async def pick_task():
            try:
                # ВОТ ОНО! Никаких overlay. FilePicker вызывается напрямую.
                files = await ft.FilePicker().pick_files(allow_multiple=False)

                if not files:
                    return

                f = files[0]
                with open(f.path, "rb") as file:
                    b64 = base64.b64encode(file.read()).decode('utf-8')

                self.show_snackbar(f"Отправка файла {f.name}...")
                await self.network.send({
                    "action": "send_file",
                    "chat_id": self.active_chat_id,
                    "filename": f.name,
                    "data": b64
                })
            except Exception as ex:
                print(f"Ошибка выбора файла: {ex}")
                self.show_snackbar("Ошибка при чтении файла!")

        self.page.run_task(pick_task)

    def handle_download_file(self, msg_id, filename):
        async def download_task():
            try:
                # Прямой вызов диалога сохранения!
                path = await ft.FilePicker().save_file(file_name=filename)

                if path:
                    self.pending_downloads[msg_id] = path
                    self.show_snackbar("Скачивание файла...")
                    await self.network.send({"action": "req_file", "msg_id": msg_id})
            except Exception as e:
                print(f"Ошибка сохранения: {e}")
                self.show_snackbar("Ошибка сохранения файла!")

        self.page.run_task(download_task)

    def handle_delete_message(self, msg_id):
        self.page.run_task(self.network.send,
                           {"action": "delete_msg", "chat_id": self.active_chat_id, "msg_id": msg_id})

    # ==========================================
    #       СЕТЕВЫЕ СОБЫТИЯ
    # ==========================================

    async def on_net_disconnect(self):
        # Если юзер сам нажал "Выйти", переподключаться не надо
        if not getattr(self, 'is_logged_in', False):
            return

        if hasattr(self, 'chat_screen'):
            self.chat_screen.add_system_message("Связь потеряна. Переподключение через 3 сек...", ft.Colors.RED)

        await asyncio.sleep(3)

        # Пытаемся переподключиться тихо (в фоне)
        response = await self.network.connect(
            self.settings.get("host"), 8888,
            self.settings.get("username"),
            self.settings.get("password")
        )

        if response.get("status") == "ok":
            self.chat_screen.add_system_message("Соединение восстановлено!", ft.Colors.GREEN)
            await self.network.send({"action": "get_chats"})
            await self.network.send({"action": "get_history", "chat_id": self.active_chat_id, "limit": 20})
            self.page.run_task(self.network.listen)
        else:
            # Если сервер все еще лежит - уходим в рекурсию (пробуем снова)
            self.page.run_task(self.on_net_disconnect)

    async def on_net_message(self, data):
        action = data.get("action")

        if action == "new_msg":
            chat_id, msg = data.get("chat_id"), data.get("message")
            chat_data = self.chats_info.get(chat_id, {})
            cname = self.get_chat_name(chat_data) if chat_data else f"ID:{chat_id}"

            is_active_chat = (chat_id == self.active_chat_id)
            is_hidden = getattr(self.page.window, "minimized", False) or not getattr(self.page.window, "visible", True)

            if is_active_chat:
                self.chat_screen.add_message(
                    sender=msg['sender'],
                    text=msg.get('text', ''),
                    timestamp=msg['timestamp'],
                    msg_id=msg.get('id'),
                    file_name=msg.get('file_name')
                )
            else:
                self.chat_screen.add_system_message(f"[🔔] Новое сообщение в чате '{cname}'", ft.Colors.YELLOW)

            if msg['sender'] != self.current_username:
                if is_hidden or not is_active_chat or self.settings.get("notify_always"):
                    notif_text = f"Отправил файл: {msg.get('file_name')}" if msg.get(
                        'file_name') else f"{msg['sender']}: {msg.get('text', '')}"
                    self.os.notify(f"Чат: {cname}", notif_text)
                    self.os.set_tray_badge(True)

        elif action == "msg_deleted":
            if data.get("chat_id") == self.active_chat_id:
                self.chat_screen.remove_message(data.get("msg_id"))

        elif action == "chat_list":
            for c in data.get("chats", []):
                self.chats_info[c['id']] = c
            self.update_drawer()

        elif action == "history":
            self.chat_screen.clear_messages()
            messages, chat_id = data.get("messages", []), data.get("chat_id")
            chat_data = self.chats_info.get(chat_id, {})
            cname = self.get_chat_name(chat_data) if chat_data else f"ID:{chat_id}"
            self.chat_screen.set_chat_title(cname)

            for msg in messages:
                self.chat_screen.add_message(
                    sender=msg['sender'],
                    text=msg.get('text', ''),
                    timestamp=msg['timestamp'],
                    msg_id=msg.get('id'),
                    file_name=msg.get('file_name')
                )

        # --- ВОССТАНОВЛЕНА ФУНКЦИЯ СОХРАНЕНИЯ ФАЙЛОВ ---
        elif action == "res_file":
            msg_id, b64_data, filename = data.get("msg_id"), data.get("data"), data.get("filename")
            save_path = self.pending_downloads.pop(msg_id, None)

            if save_path and b64_data:
                try:
                    with open(save_path, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                    self.os.notify("Файл сохранен!", f"{filename} успешно скачан.")
                except Exception as e:
                    print(f"Ошибка сохранения файла: {e}")

    def update_drawer(self):
        # Функция для кнопки закрытия
        def _close_drawer_btn(e):
            async def close_task():
                if self.page.drawer:
                    await self.page.close_drawer()
            self.page.run_task(close_task)

        # Теперь в заголовке кнопка-бургер и текст (используем безопасный padding=10)
        controls = [
            ft.Container(
                padding=10,  # <--- ИСПРАВЛЕНО: просто число вместо ft.padding.only
                content=ft.Row([
                    ft.IconButton(icon=ft.Icons.MENU, on_click=_close_drawer_btn),
                    ft.Text("Меню", size=20, weight="bold")
                ])
            )
        ]

        saved_id = None
        for cid, chat in self.chats_info.items():
            if chat.get('type') == 'saved':
                saved_id = cid
                break

        def make_select(cid):
            return lambda e: self.handle_select_chat(cid)

        controls.append(
            ft.ListTile(leading=ft.Icon(ft.Icons.GROUP), title=ft.Text("Общий чат"), on_click=make_select(1)))
        if saved_id:
            controls.append(ft.ListTile(leading=ft.Icon(ft.Icons.BOOKMARK), title=ft.Text("Избранное"),
                                        on_click=make_select(saved_id)))
        controls.append(ft.Divider())

        has_dialogs = False
        for cid, chat in self.chats_info.items():
            if chat.get('type') == 'dialog':
                has_dialogs = True
                display_name = self.get_chat_name(chat)
                controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.PERSON),
                        title=ft.Text(display_name),
                        on_click=make_select(cid)
                    )
                )

        if not has_dialogs:
            controls.append(ft.Container(padding=15, content=ft.Text("Нет личных сообщений", color=ft.Colors.GREY_500)))
        controls.append(ft.Divider())

        controls.append(ft.ListTile(leading=ft.Icon(ft.Icons.ADD), title=ft.Text("Создать диалог"),
                                    on_click=lambda e: self.show_pm_modal()))
        controls.append(ft.ListTile(leading=ft.Icon(ft.Icons.SETTINGS), title=ft.Text("Настройки"),
                                    on_click=lambda e: self.show_settings_modal()))

        if not self.page.drawer:
            self.page.drawer = ft.NavigationDrawer(controls=controls)
        else:
            self.page.drawer.controls = controls

        self.page.update()

    def handle_select_chat(self, chat_id):
        async def close_task():
            if self.page.drawer:
                await self.page.close_drawer()

        # Закрываем меню асинхронно
        self.page.run_task(close_task)

        # Остальной код без изменений
        self.active_chat_id = chat_id
        self.os.set_tray_badge(False)
        self.page.run_task(self.network.send, {"action": "get_history", "chat_id": chat_id, "limit": 20})