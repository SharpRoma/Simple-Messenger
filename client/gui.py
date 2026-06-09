import flet as ft
from datetime import datetime
import config
from network import MessengerNetwork


class MessengerGUI:
    def __init__(self, page: ft.Page, notify_os_callback, tray_badge_callback):
        self.page = page
        self.notify_os = notify_os_callback
        self.set_tray_badge = tray_badge_callback

        self.network = MessengerNetwork(self.on_net_message, self.on_net_disconnect)
        self.active_chat_id = 1
        self.chats_info = {}
        self.is_pinned = False
        self.settings = config.load_settings()

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

    def close_dialog(self, dlg):
        dlg.open = False
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
        self.page.clean()
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER

        self.host_input = ft.TextField(label="IP сервера", value=self.settings.get("host"), width=300,
                                       on_submit=lambda e: self.user_input.focus())
        self.user_input = ft.TextField(label="Логин", value=self.settings.get("username"), width=300,
                                       on_submit=lambda e: self.pass_input.focus())
        self.pass_input = ft.TextField(label="Пароль", password=True, value=self.settings.get("password"), width=300,
                                       on_submit=self.connect_to_server)
        self.auto_login_checkbox = ft.Checkbox(label="Входить автоматически", value=self.settings.get("auto_login"))
        self.login_err = ft.Text(color="red")

        self.page.add(ft.Text("Вход в Messenger", size=24, weight="bold"), self.host_input, self.user_input,
                      self.pass_input, self.auto_login_checkbox, self.login_err,
                      self.btn_class("Подключиться", on_click=self.connect_to_server))

    def show_chat_screen(self):
        self.page.clean()
        self.page.horizontal_alignment = ft.CrossAxisAlignment.START
        self.page.vertical_alignment = ft.MainAxisAlignment.START

        self.chat_history = ft.ListView(expand=True, spacing=5, auto_scroll=True)
        self.msg_input = ft.TextField(hint_text="Написать сообщение...", expand=True, on_submit=self.send_message_ui,
                                      on_focus=lambda e: self.set_tray_badge(False))
        self.pin_btn = ft.IconButton(icon=ft.Icons.PUSH_PIN, icon_color=ft.Colors.WHITE54, tooltip="Поверх всех окон",
                                     on_click=self.toggle_pin)
        self.settings_btn = ft.IconButton(icon=ft.Icons.SETTINGS, tooltip="Настройки",
                                          on_click=lambda e: self.show_settings_modal())

        buttons_row = ft.Row([self.btn_class("Чаты", icon=ft.Icons.LIST, on_click=self.btn_click_chats),
                              self.btn_class("Личка", icon=ft.Icons.PERSON_ADD, on_click=self.show_pm_modal),
                              self.settings_btn, self.pin_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        main_layout = ft.Column([buttons_row, ft.Divider(),
                                 ft.Container(content=self.chat_history, expand=True, border_radius=5, padding=10,
                                              bgcolor="#1e1e1e"), ft.Row([self.msg_input,
                                                                          ft.IconButton(icon=ft.Icons.SEND,
                                                                                        icon_color=ft.Colors.BLUE,
                                                                                        on_click=self.send_message_ui)])],
                                expand=True)

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

    def print_to_console(self, text, color=ft.Colors.WHITE, copy_text=None):
        try:
            if copy_text:
                def make_copy_handler(t):
                    async def handler(e): await self.copy_to_clipboard(t)

                    return handler

                row = ft.Row([ft.Text(text, color=color, font_family="Consolas", selectable=True, expand=True),
                              ft.IconButton(icon=ft.Icons.COPY, icon_size=16, icon_color=ft.Colors.GREY_600,
                                            tooltip="Скопировать", on_click=make_copy_handler(copy_text))],
                             alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                self.chat_history.controls.append(row)
            else:
                self.chat_history.controls.append(ft.Text(text, color=color, font_family="Consolas", selectable=True))
            self.chat_history.update()
        except:
            pass

    async def connect_to_server(self, e=None):
        host, username, password = self.host_input.value, self.user_input.value, self.pass_input.value
        if e is not None:
            self.settings.update(
                {"host": host, "username": username, "password": password if self.auto_login_checkbox.value else "",
                 "auto_login": self.auto_login_checkbox.value})
            config.save_settings(self.settings)

        self.login_err.value = "Подключение..."
        self.page.update()

        response = await self.network.connect(host, 8888, username, password)
        if response.get("status") != "ok":
            self.login_err.value = f"Ошибка: {response.get('msg')}"
            if self.settings["auto_login"]:
                self.settings["auto_login"] = False
                config.save_settings(self.settings)
            self.page.update()
            return

        self.show_chat_screen()
        await self.network.send({"action": "get_chats"})
        await self.network.send({"action": "get_history", "chat_id": 1, "limit": 20, "offset": 0})
        self.page.run_task(self.network.listen)

    async def on_net_disconnect(self):
        self.print_to_console("❌ Соединение разорвано.", ft.Colors.RED)

    async def on_net_message(self, data):
        action = data.get("action")
        if action == "new_msg":
            chat_id, msg = data.get("chat_id"), data.get("message")
            ts = datetime.fromtimestamp(msg.get("timestamp")).strftime('%H:%M')
            cname = self.chats_info.get(chat_id, {}).get("name", f"ID:{chat_id}")
            sender, text = msg['sender'], msg['text']

            is_active_chat = (chat_id == self.active_chat_id)
            is_window_hidden = getattr(self.page.window, "minimized", False) or not getattr(self.page.window, "visible",
                                                                                            True)
            my_username = self.settings.get("username")

            if is_active_chat:
                self.print_to_console(f"[{ts}] {sender}: {text}", copy_text=text)
            else:
                self.print_to_console(f"[🔔] Новое сообщение в чате '{cname}'", ft.Colors.YELLOW)

            if sender != my_username:
                if is_window_hidden or not is_active_chat or self.settings.get("notify_always"):
                    self.notify_os(f"Чат: {cname}", f"{sender}: {text}")
                    self.set_tray_badge(True)

        elif action == "history":
            self.chat_history.controls.clear()
            messages, chat_id = data.get("messages", []), data.get("chat_id")
            cname = self.chats_info.get(chat_id, {}).get("name", f"ID:{chat_id}")
            self.print_to_console(f"--- Вы в чате '{cname}' ---", ft.Colors.BLUE_200)
            for msg in messages:
                ts = datetime.fromtimestamp(msg.get("timestamp")).strftime('%H:%M')
                self.print_to_console(f"[{ts}] {msg['sender']}: {msg['text']}", copy_text=msg['text'])

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