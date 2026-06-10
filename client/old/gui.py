import flet as ft
import asyncio
from datetime import datetime
import config
from network import MessengerNetwork
import base64


class MessengerGUI:
    def __init__(self, page: ft.Page, notify_os_callback, tray_badge_callback):
        self.page = page
        self.notify_os = notify_os_callback
        self.set_tray_badge = tray_badge_callback

        self.network = MessengerNetwork(self.on_net_message, self.on_net_disconnect)
        self.active_chat_id = 1
        self.chats_info = {}
        self.current_username = ""
        self.is_pinned = False
        self.settings = config.load_settings()
        self.pending_downloads = {}

        self.page.title = "Simple Messenger"
        self.page.window.width = 400
        self.page.window.height = 550
        self.page.window.min_width = 350
        self.page.window.min_height = 400
        self.page.theme_mode = ft.ThemeMode.DARK
        self.btn_class = getattr(ft, 'Button', ft.ElevatedButton)

        self.show_login_screen()
        if self.settings.get("auto_login") and self.settings.get("username"):
            self.page.run_task(self.connect_to_server)

    async def on_attach_click(self, e):
        try:
            files = await ft.FilePicker().pick_files()
            if files:
                f = files[0]
                with open(f.path, "rb") as file:
                    b64 = base64.b64encode(file.read()).decode('utf-8')

                snack = ft.SnackBar(ft.Text(f"Отправка файла {f.name}..."))
                self.page.overlay.append(snack)
                snack.open = True
                self.page.update()

                await self.network.send(
                    {"action": "send_file", "chat_id": self.active_chat_id, "filename": f.name, "data": b64})
        except Exception as ex:
            print(f"Ошибка выбора файла: {ex}")

    def close_dialog(self, dlg):
        """ПРАВИЛЬНОЕ закрытие диалога, чтобы Flet успел проиграть анимацию исчезновения"""
        dlg.open = False
        self.page.update()

        # Удаляем окно из памяти только через 0.2 секунды
        async def remove_later():
            await asyncio.sleep(0.2)
            if dlg in self.page.overlay:
                self.page.overlay.remove(dlg)
                self.page.update()

        self.page.run_task(remove_later)

    def confirm_delete_msg(self, msg_id):
        dlg = ft.AlertDialog(title=ft.Text("Удаление"), content=ft.Text("Удалить сообщение для всех участников?"))

        async def on_confirm(e):
            self.close_dialog(dlg)
            await self.network.send({"action": "delete_msg", "chat_id": self.active_chat_id, "msg_id": msg_id})

        dlg.actions = [ft.TextButton("Удалить", on_click=on_confirm, style=ft.ButtonStyle(color=ft.Colors.RED)),
                       ft.TextButton("Отмена", on_click=lambda e: self.close_dialog(dlg))]
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def show_register_modal(self):
        reg_user = ft.TextField(label="Придумайте логин", autofocus=True)
        reg_pass = ft.TextField(label="Придумайте пароль", password=True)
        reg_secret = ft.TextField(label="Секретный код сервера", password=True)
        reg_err = ft.Text(color="red")

        async def on_submit(e):
            username = reg_user.value.strip()
            password = reg_pass.value.strip()
            secret = reg_secret.value.strip()

            if not username or not password or not secret:
                reg_err.value = "Заполните все поля!"
                self.page.update()
                return

            # Копируем введенные данные в основные поля формы
            self.user_input.value = username
            self.pass_input.value = password

            # Ждем окончания подключения
            success = await self.connect_to_server(mode="register", secret=secret)

            # Если подключение успешно - только тогда закрываем окно регистрации!
            if success:
                self.close_dialog(dlg)
            else:
                reg_err.value = "Проверьте данные, возникла ошибка."
                self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Регистрация аккаунта"),
            content=ft.Column([reg_user, reg_pass, reg_secret, reg_err], tight=True),
            actions=[ft.TextButton("Зарегистрироваться", on_click=on_submit),
                     ft.TextButton("Отмена", on_click=lambda e: self.close_dialog(dlg))]
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def show_settings_modal(self):
        def on_autostart_change(e):
            self.settings["auto_start"] = autostart_switch.value
            config.set_autostart(autostart_switch.value)
            config.save_settings(self.settings)

        def on_notify_change(e):
            self.settings["notify_always"] = notify_switch.value
            config.save_settings(self.settings)

        async def on_logout(e):
            self.settings["auto_login"] = False
            self.settings["password"] = ""
            config.save_settings(self.settings)
            await self.network.disconnect()
            self.close_dialog(dlg)
            self.show_login_screen()

        autostart_switch = ft.Switch(label="Автозапуск", value=self.settings.get("auto_start", False),
                                     on_change=on_autostart_change)
        notify_switch = ft.Switch(label="Уведомлять при открытом чате", value=self.settings.get("notify_always", False),
                                  on_change=on_notify_change)
        logout_btn = ft.ElevatedButton("Выйти", color=ft.Colors.RED, on_click=on_logout)

        dlg = ft.AlertDialog(title=ft.Text("Настройки", weight="bold"),
                             content=ft.Column([autostart_switch, notify_switch, ft.Divider(), logout_btn], tight=True),
                             actions=[ft.TextButton("Закрыть", on_click=lambda e: self.close_dialog(dlg))])
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def show_pm_modal(self):
        pm_input = ft.TextField(label="Логин", autofocus=True)

        async def on_submit(e):
            target = pm_input.value.strip()
            self.close_dialog(dlg)
            if target: await self.network.send({"action": "create_dialog", "target": target})

        dlg = ft.AlertDialog(title=ft.Text("Новый диалог"), content=pm_input,
                             actions=[ft.TextButton("Создать", on_click=on_submit),
                                      ft.TextButton("Отмена", on_click=lambda e: self.close_dialog(dlg))])
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def show_chats_modal(self, chats_data):
        list_view = ft.ListView(expand=True, spacing=10)
        dlg = ft.AlertDialog(title=ft.Text("Выберите чат"),
                             content=ft.Container(content=list_view, width=300, height=300),
                             actions=[ft.TextButton("Закрыть", on_click=lambda e: self.close_dialog(dlg))])
        for c in chats_data:
            cid, cname, ctype = c['id'], c['name'], c['type']
            icon = ft.Icons.GROUP if ctype == 'global' else ft.Icons.PERSON if ctype == 'dialog' else ft.Icons.BOOKMARK

            def make_click_handler(chat_id):
                async def handler(e):
                    self.close_dialog(dlg)
                    self.active_chat_id = chat_id
                    self.set_tray_badge(False)
                    await self.network.send({"action": "get_history", "chat_id": chat_id, "limit": 20})

                return handler

            list_view.controls.append(ft.ListTile(leading=ft.Icon(icon), title=ft.Text(cname), subtitle=ft.Text(
                "Текущий" if cid == self.active_chat_id else f"Тип: {ctype}"), on_click=make_click_handler(cid)))
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def show_login_screen(self):
        self.page.title = "Simple Messenger"
        self.page.clean()
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER

        # Правильные асинхронные обработчики для Enter
        async def focus_user(e): await self.user_input.focus()

        async def focus_pass(e): await self.pass_input.focus()

        async def submit_login(e): await self.connect_to_server()

        self.host_input = ft.TextField(label="IP сервера", value=self.settings.get("host"), width=300,
                                       on_submit=focus_user)
        self.user_input = ft.TextField(label="Логин", value=self.settings.get("username"), width=300,
                                       on_submit=focus_pass)
        self.pass_input = ft.TextField(label="Пароль", password=True, value=self.settings.get("password"), width=300,
                                       on_submit=submit_login)
        self.auto_login_checkbox = ft.Checkbox(label="Входить автоматически", value=self.settings.get("auto_login"))
        self.login_err = ft.Text(color="red")

        btns = ft.Row([
            self.btn_class("Вход", on_click=submit_login),
            ft.TextButton("Регистрация", on_click=lambda e: self.show_register_modal())
        ], alignment=ft.MainAxisAlignment.CENTER)

        self.page.add(
            ft.Text("Messenger", size=24, weight="bold"),
            self.host_input,
            self.user_input,
            self.pass_input,
            self.auto_login_checkbox,
            self.login_err,
            btns
        )

    def show_chat_screen(self):
        self.page.clean()
        self.page.horizontal_alignment = ft.CrossAxisAlignment.START
        self.page.vertical_alignment = ft.MainAxisAlignment.START

        self.chat_history = ft.ListView(expand=True, spacing=5, auto_scroll=True)
        self.msg_input = ft.TextField(hint_text="Написать сообщение...", expand=True, on_submit=self.send_message_ui,
                                      on_focus=lambda e: self.set_tray_badge(False))
        self.pin_btn = ft.IconButton(icon=ft.Icons.PUSH_PIN, icon_color=ft.Colors.WHITE54, tooltip="Поверх всех",
                                     on_click=self.toggle_pin)
        self.settings_btn = ft.IconButton(icon=ft.Icons.SETTINGS, tooltip="Настройки",
                                          on_click=lambda e: self.show_settings_modal())

        buttons_row = ft.Row([self.btn_class("Чаты", icon=ft.Icons.LIST, on_click=self.btn_click_chats),
                              self.btn_class("Личка", icon=ft.Icons.PERSON_ADD,
                                             on_click=lambda e: self.show_pm_modal()), self.settings_btn, self.pin_btn],
                             alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        input_row = ft.Row([
            ft.IconButton(icon=ft.Icons.ATTACH_FILE, icon_color=ft.Colors.GREY_400, on_click=self.on_attach_click),
            self.msg_input,
            ft.IconButton(icon=ft.Icons.SEND, icon_color=ft.Colors.BLUE, on_click=self.send_message_ui)
        ])

        main_layout = ft.Column([buttons_row, ft.Divider(),
                                 ft.Container(content=self.chat_history, expand=True, border_radius=5, padding=10,
                                              bgcolor="#1e1e1e"), input_row], expand=True)

        self.page.add(main_layout)
        self.page.update()

    async def toggle_pin(self, e):
        self.is_pinned = not self.is_pinned
        self.page.window.always_on_top = self.is_pinned
        self.pin_btn.icon_color = ft.Colors.RED if self.is_pinned else ft.Colors.WHITE54
        self.page.update()

    async def copy_to_clipboard(self, text):
        try:
            if hasattr(ft, 'Clipboard'):
                await ft.Clipboard().set(text)
            else:
                self.page.set_clipboard(text)
            snack = ft.SnackBar(ft.Text("Скопировано!"), duration=1500)
            self.page.overlay.append(snack)
            snack.open = True
            self.page.update()
        except:
            pass

    def print_to_console(self, text, color=ft.Colors.WHITE, copy_text=None, msg_id=None, is_own=False, file_name=None):
        try:
            actions = []
            if file_name:
                content = ft.Text(f"📎 Файл: {file_name}", color=ft.Colors.BLUE_200, italic=True, expand=True)

                def make_download_handler(mid, fname):
                    async def handler(e):
                        try:
                            path = await ft.FilePicker().save_file(file_name=fname)
                            if path:
                                self.pending_downloads[mid] = path
                                snack = ft.SnackBar(ft.Text("Скачивание файла..."))
                                self.page.overlay.append(snack)
                                snack.open = True
                                self.page.update()
                                await self.network.send({"action": "req_file", "msg_id": mid})
                        except Exception as e:
                            print(f"Ошибка сохранения: {e}")

                    return handler

                actions.append(ft.IconButton(icon=ft.Icons.DOWNLOAD, icon_size=16, tooltip="Скачать",
                                             on_click=make_download_handler(msg_id, file_name)))
            else:
                content = ft.Text(text, color=color, font_family="Consolas", selectable=True, expand=True)
                if copy_text:
                    def make_copy_handler(t):
                        async def handler(e): await self.copy_to_clipboard(t)

                        return handler

                    actions.append(ft.IconButton(icon=ft.Icons.COPY, icon_size=16, icon_color=ft.Colors.GREY_600,
                                                 tooltip="Копировать", on_click=make_copy_handler(copy_text)))

            if is_own and msg_id:
                def make_del_handler(mid):
                    async def handler(e): self.confirm_delete_msg(mid)

                    return handler

                actions.append(ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_size=16, icon_color=ft.Colors.RED_400,
                                             tooltip="Удалить", on_click=make_del_handler(msg_id)))

            row_controls = [content] + actions
            row = ft.Row(row_controls, alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                         key=f"msg_{msg_id}" if msg_id else None)
            self.chat_history.controls.append(row)
            self.chat_history.update()
        except:
            pass

    async def connect_to_server(self, mode="login", secret=""):
        host, username, password = self.host_input.value.strip(), self.user_input.value.strip(), self.pass_input.value.strip()

        if not host or not username or not password:
            self.login_err.value = "Заполните все поля!"
            self.page.update()
            return False

        self.login_err.value = "Подключение..."
        self.page.update()

        response = await self.network.connect(host, 8888, username, password, mode=mode, secret=secret)
        if response.get("status") != "ok":
            self.login_err.value = f"Ошибка: {response.get('msg')}"

            snack = ft.SnackBar(ft.Text(f"Ошибка: {response.get('msg')}", color=ft.Colors.WHITE),
                                bgcolor=ft.Colors.RED_700)
            self.page.overlay.append(snack)
            snack.open = True

            if self.settings.get("auto_login"):
                self.settings["auto_login"] = False
                config.save_settings(self.settings)
            self.page.update()
            return False

        self.current_username = username
        self.page.title = f"Simple Messenger ({self.current_username})"

        if mode == "login" or mode == "register":
            self.settings.update(
                {"host": host, "username": username, "password": password if self.auto_login_checkbox.value else "",
                 "auto_login": self.auto_login_checkbox.value})
            config.save_settings(self.settings)

        self.show_chat_screen()
        await self.network.send({"action": "get_chats"})
        await self.network.send({"action": "get_history", "chat_id": 1, "limit": 20, "offset": 0})
        self.page.run_task(self.network.listen)
        return True

    async def on_net_disconnect(self):
        self.print_to_console("❌ Соединение разорвано.", ft.Colors.RED)

    async def on_net_message(self, data):
        action = data.get("action")

        if action == "res_file":
            msg_id, b64_data, filename = data.get("msg_id"), data.get("data"), data.get("filename")
            save_path = self.pending_downloads.pop(msg_id, None)

            if save_path and b64_data:
                try:
                    with open(save_path, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                    self.notify_os("Файл сохранен!", f"{filename} успешно скачан.")
                except Exception as e:
                    print(f"Ошибка сохранения файла: {e}")

        elif action == "new_msg":
            chat_id, msg = data.get("chat_id"), data.get("message")
            ts = datetime.fromtimestamp(msg.get("timestamp")).strftime('%H:%M')
            cname = self.chats_info.get(chat_id, {}).get("name", f"ID:{chat_id}")
            sender, text, msg_id, file_name = msg['sender'], msg.get('text', ''), msg.get('id'), msg.get('file_name')

            is_active_chat = (chat_id == self.active_chat_id)
            is_window_hidden = getattr(self.page.window, "minimized", False) or not getattr(self.page.window, "visible",
                                                                                            True)

            if is_active_chat:
                self.print_to_console(f"[{ts}] {sender}: {text}", copy_text=text if not file_name else None,
                                      msg_id=msg_id, is_own=(sender == self.current_username), file_name=file_name)
            else:
                self.print_to_console(f"[🔔] Новое сообщение в чате '{cname}'", ft.Colors.YELLOW)

            if sender != self.current_username:
                if is_window_hidden or not is_active_chat or self.settings.get("notify_always"):
                    notif_text = f"Отправил файл: {file_name}" if file_name else f"{sender}: {text}"
                    self.notify_os(f"Чат: {cname}", notif_text)
                    self.set_tray_badge(True)

        elif action == "msg_deleted":
            msg_id = data.get("msg_id")
            if data.get("chat_id") == self.active_chat_id:
                for ctrl in self.chat_history.controls:
                    if getattr(ctrl, "key", None) == f"msg_{msg_id}":
                        self.chat_history.controls.remove(ctrl)
                        self.chat_history.update()
                        break

        elif action == "history":
            self.chat_history.controls.clear()
            messages, chat_id = data.get("messages", []), data.get("chat_id")
            cname = self.chats_info.get(chat_id, {}).get("name", f"ID:{chat_id}")

            self.print_to_console(f"--- Вы в чате '{cname}' ---", ft.Colors.BLUE_200)
            for msg in messages:
                ts = datetime.fromtimestamp(msg.get("timestamp")).strftime('%H:%M')
                self.print_to_console(f"[{ts}] {msg['sender']}: {msg.get('text', '')}",
                                      copy_text=msg.get('text') if not msg.get('file_name') else None,
                                      msg_id=msg.get("id"), is_own=(msg['sender'] == self.current_username),
                                      file_name=msg.get('file_name'))

        elif action == "chat_list":
            for c in data.get("chats", []): self.chats_info[c['id']] = c
            if getattr(self, "_show_chats_modal_flag", False):
                self._show_chats_modal_flag = False
                self.show_chats_modal(data.get("chats", []))

        elif action == "dialog_created":
            new_id, target = data.get("chat_id"), data.get("target")
            self.print_to_console(f"✅ Создан диалог с {target}.", ft.Colors.GREEN)
            await self.network.send({"action": "get_chats"})
            self.active_chat_id = new_id
            await self.network.send({"action": "get_history", "chat_id": new_id, "limit": 20})

    async def btn_click_chats(self, e):
        self._show_chats_modal_flag = True
        await self.network.send({"action": "get_chats"})

    async def send_message_ui(self, e):
        text = self.msg_input.value.strip()
        if not text: return
        self.msg_input.value = ""
        self.page.update()
        if text.startswith('/'):
            parts = text.split()
            cmd = parts[0].lower()
            if cmd == '/chats':
                self._show_chats_modal_flag = True
                await self.network.send({"action": "get_chats"})
            elif cmd == '/pm' and len(parts) > 1:
                await self.network.send({"action": "create_dialog", "target": parts[1]})
        else:
            await self.network.send({"action": "send_msg", "chat_id": self.active_chat_id, "text": text})