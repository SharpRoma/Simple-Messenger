import flet as ft
import asyncio
import base64
import time
import os
from datetime import datetime
from network import MessengerNetwork
from ui.screens.login_screen import LoginScreen
from ui.screens.chat_screen import ChatScreen
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.pm_dialog import PmDialog
from ui.dialogs.register_dialog import RegisterDialog

from ui.dialogs.create_group_dialog import CreateGroupDialog
from ui.dialogs.add_member_dialog import AddMemberDialog

from ui.dialogs.chat_profile_dialog import ChatProfileDialog
from ui.dialogs.restore_dialog import RestoreDialog
from ui.dialogs.media_dialog import MediaDialog

from database import ClientDatabase
from system.crypto import CryptoManager
import logging

logger = logging.getLogger("messenger.main")

class MainWindow:
    def __init__(self, page: ft.Page, system_adapter, settings_manager):
        self.page = page
        self.os = system_adapter
        self.settings_manager = settings_manager
        self.settings = self.settings_manager.load_settings()

        self.db = ClientDatabase(self.settings_manager.APP_DIR / "client_cache.sqlite")
        self.crypto_mgr = CryptoManager(self.settings_manager.APP_DIR)

        self.current_username = ""
        self.active_chat_id = None
        self.chats_info = {}
        self.users_status = {}
        self.history_offset = 0
        self.is_loading_history = False
        self.has_more_history = True
        self.pending_downloads = {}
        self.is_reconnecting = False

        self.network = MessengerNetwork(self.on_net_message, self.on_net_disconnect)

        self.page.title = "Simple Messenger"
        self.page.window.width = 400
        self.page.window.height = 550
        self.page.window.min_width = 350
        self.page.window.min_height = 400
        self.page.theme_mode = ft.ThemeMode.DARK

        self.page.drawer = ft.NavigationDrawer(controls=[])
        self.page.on_keyboard_event = self.handle_keyboard_event

        self.show_login_screen()

        if self.settings.get("auto_login") and self.settings.get("username"):
            self.auto_connect()

        self.last_typing_sent = 0
        self.typing_timers = {}

        self.editing_msg_id = None
        self.editing_delete_file = False
        self.editing_new_file = None
        self.is_searching = False

    def get_chat_name(self, chat_data: dict) -> str:
        """Форматирует имя чата для отображения, даже если в логинах есть спецсимволы"""
        name = chat_data.get('name', 'Неизвестный чат')

        if chat_data.get('type') in ['dialog', 'secret']:
            # Чат может называться "мойЛогин_чужойЛогин" или "чужойЛогин_мойЛогин"
            prefix = f"{self.current_username}_"
            suffix = f"_{self.current_username}"

            if name.startswith(prefix):
                return name[len(prefix):]  # Отрезаем спереди
            elif name.endswith(suffix):
                return name[:-len(suffix)]  # Отрезаем сзади

        return name

    def handle_keyboard_event(self, e: ft.KeyboardEvent):
        if e.key == "Escape" and self.is_logged_in and self.page.drawer:
            async def toggle_drawer():
                if self.page.drawer.open:
                    await self.page.close_drawer()
                else:
                    await self.page.show_drawer()
            self.page.run_task(toggle_drawer)

    def show_login_screen(self):
        self.page.clean()
        self.page.drawer = None
        self.is_logged_in = False

        self.current_username = ""
        self.active_chat_id = None
        self.chats_info = {}
        self.pending_downloads = {}
        self.users_status = {}

        self.login_screen = LoginScreen(
            settings=self.settings,
            on_login_callback=self.handle_login,
            on_show_register_callback=self.show_register_modal,
            on_show_restore_callback = self.show_restore_modal
        )
        self.page.add(self.login_screen)
        self.last_typing_sent = 0
        self.typing_timers = {}

    def show_chat_screen(self):
        self.page.clean()

        def open_menu():
            async def open_task():
                if self.page.drawer:
                    # УБРАЛИ АРГУМЕНТ ИЗ СКОБОК!
                    await self.page.show_drawer()

            self.page.run_task(open_task)

        def handle_typing():
            if not self.active_chat_id: return
            # Отправляем на сервер максимум 1 раз в 2 секунды
            now = time.time()
            if now - self.last_typing_sent > 2:
                self.last_typing_sent = now
                self.page.run_task(self.network.send, {"action": "typing", "chat_id": self.active_chat_id})

        self.chat_screen = ChatScreen(
            current_username=self.current_username,
            on_send_message=self.handle_send_message,
            on_typing=handle_typing,
            on_attach_file=self.handle_attach_file,
            on_open_drawer=open_menu,
            on_toggle_pin=self.handle_toggle_pin,
            on_copy_message=self.handle_copy_message,
            on_delete_message=self.handle_delete_message,
            on_download_file=self.handle_download_file,
            on_input_focus=lambda: self.os.set_tray_badge(False),
            on_open_profile = self.handle_open_profile,
            on_load_more_history=self.handle_load_more_history,
            on_get_media_url=self.get_media_url,
            on_open_media=self.show_media_modal,
            on_edit_message=self.handle_edit_message,
            on_cancel_edit=self.handle_cancel_edit,
            on_delete_attached_file=self.handle_delete_attached_file,
            on_search_messages=self.handle_search_messages,
            on_clear_search=self.handle_clear_search
        )
        self.page.add(self.chat_screen)

        # Сначала загружаем чаты из локальной БД
        cached_chats = self.db.get_chats()
        if cached_chats:
            for c in cached_chats:
                self.chats_info[c['id']] = c

            # Если активный чат еще не выбран, выберем первый/избранный из кэша
            chat_to_select = self.active_chat_id
            if not chat_to_select:
                saved_chat = next((c for c in cached_chats if c.get('type') == 'saved'), None)
                chat_to_select = saved_chat['id'] if saved_chat else cached_chats[0]['id']

            self.handle_select_chat(chat_to_select)

        self.update_drawer()

    def handle_login(self, host, port, username, password, auto_login):
        async def login_task():
            # Обязательно переводим порт в int() !
            response = await self.network.connect(host, int(port), username, password)

            if response.get("status") != "ok":
                # Если сервер недоступен, но у нас включен автологин, заходим в оффлайн-режиме
                if response.get("msg") == "Сервер недоступен" and auto_login:
                    self.current_username = username
                    self.is_logged_in = True
                    self.page.title = f"Simple Messenger ({self.current_username}) [Offline]"
                    self.show_chat_screen()
                    self.page.run_task(self.on_net_disconnect)
                    return

                self.login_screen.show_error(f"Ошибка: {response.get('msg')}")
                return

            self.current_username = username
            self.settings.update({
                "host": host,
                "port": port,
                "username": username,
                "password": password if auto_login else "",
                "auto_login": auto_login
            })
            self.settings_manager.save_settings(self.settings)

            self.is_logged_in = True
            self.page.title = f"Simple Messenger ({self.current_username})"

            self.show_chat_screen()

            # Инициализация и загрузка публичного ключа для E2EE
            try:
                self.crypto_mgr.init_keys()
                pubkey = self.crypto_mgr.get_public_key_pem()
                await self.network.upload_public_key(pubkey)
            except Exception as e:
                logger.error(f"Failed to upload E2EE public key: {e}", exc_info=True)

            await self.network.send({"action": "get_chats"})

            self.page.run_task(self.network.listen)

        self.page.run_task(login_task)

    def auto_connect(self):
        self.handle_login(
            self.settings.get("host"),
            self.settings.get("port"),
            self.settings.get("username"),
            self.settings.get("password"),
            True
        )

    def handle_send_message(self, text: str):
        if not self.active_chat_id: return
        if not self.network.ws:
            self.show_snackbar("Нет подключения к сети!")
            return
        async def send_task():
            chat_data = self.chats_info.get(self.active_chat_id, {})
            is_secret = chat_data.get("type") == "secret"
            sym_key_b64 = chat_data.get("symmetric_key")

            if self.editing_msg_id is not None:
                msg_id = self.editing_msg_id
                delete_file = self.editing_delete_file
                new_filepath = self.editing_new_file
                new_filename = getattr(self, "editing_new_filename", None)
                
                self.handle_cancel_edit()

                payload_text = text
                if is_secret and sym_key_b64:
                    try:
                        key_bytes = base64.b64decode(sym_key_b64)
                        payload_text = CryptoManager.encrypt_aes(key_bytes, text)
                    except Exception as e:
                        logger.error(f"Failed to encrypt edited message: {e}", exc_info=True)
                
                await self.network.send({
                    "action": "edit_msg",
                    "msg_id": msg_id,
                    "text": payload_text,
                    "delete_file": delete_file,
                    "new_filepath": new_filepath,
                    "new_filename": new_filename
                })
            else:
                if text.startswith('/'):
                    parts = text.split()
                    cmd = parts[0].lower()
                    if cmd == '/chats':
                        self.page.run_task(self.network.send, {"action": "get_chats"})
                    elif cmd == '/pm' and len(parts) > 1:
                        await self.network.send({"action": "create_dialog", "target": parts[1]})
                else:
                    payload_text = text
                    if is_secret and sym_key_b64:
                        try:
                            key_bytes = base64.b64decode(sym_key_b64)
                            payload_text = CryptoManager.encrypt_aes(key_bytes, text)
                        except Exception as e:
                            logger.error(f"Failed to encrypt message: {e}", exc_info=True)
                    await self.network.send({"action": "send_msg", "chat_id": self.active_chat_id, "text": payload_text})

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
        current_port = self.login_screen.port_input.value.strip()

        async def on_register(host, port, username, password, secret):
            response = await self.network.connect(host, port, username, password, mode="register", secret=secret)
            if response.get("status") != "ok":
                return False, response.get('msg', 'Неизвестная ошибка')

            self.login_screen.host_input.value = host
            self.login_screen.port_input.value = port
            self.login_screen.user_input.value = username
            self.login_screen.pass_input.value = password
            self.page.update()

            self.handle_login(host, port, username, password, self.login_screen.auto_login_checkbox.value)
            return True, ""

        dialog = RegisterDialog(self.page, current_host, current_port, on_register)
        dialog.show()

    def show_restore_modal(self):
        current_host = self.login_screen.host_input.value.strip()
        current_port = self.login_screen.port_input.value.strip() or "8888"

        async def on_restore(host, port, username, password, secret):
            response = await self.network.connect(host, int(port), username, password, mode="reset", secret=secret)
            if response.get("status") != "ok":
                return False, response.get('msg', 'Неизвестная ошибка')

            # Успешно сбросили! Подставляем новые данные в форму входа
            self.login_screen.host_input.value = host
            self.login_screen.port_input.value = port
            self.login_screen.user_input.value = username
            self.login_screen.pass_input.value = password
            self.page.update()

            self.show_snackbar("Пароль изменен! Выполняется вход...", ft.Colors.GREEN)

            # Сразу логинимся с новым паролем
            self.handle_login(host, port, username, password, self.login_screen.auto_login_checkbox.value)
            return True, ""

        dialog = RestoreDialog(self.page, current_host, current_port, on_restore)
        dialog.show()

    def show_pm_modal(self):
        def on_create_pm(target_username, is_secret=False):
            if is_secret:
                self.page.run_task(self.handle_create_secret_chat, target_username)
            else:
                self.page.run_task(self.network.send, {"action": "create_dialog", "target": target_username})

        dialog = PmDialog(self.page, on_create_pm, self.handle_search_users)
        dialog.show()

    async def handle_create_secret_chat(self, target_username):
        self.show_snackbar("Запрос публичного ключа собеседника...", ft.Colors.BLUE)
        target_pubkey = await self.network.get_user_public_key(target_username)
        if not target_pubkey:
            self.show_snackbar(f"Пользователь {target_username} не поддерживает E2EE.", ft.Colors.RED)
            return

        try:
            self.crypto_mgr.init_keys()
            our_pubkey = self.crypto_mgr.get_public_key_pem()

            # Генерируем 32-байтный AES-ключ
            aes_key = os.urandom(32)
            aes_key_base64 = base64.b64encode(aes_key).decode("utf-8")

            # Шифруем ключ для себя и собеседника
            enc_key_sender = CryptoManager.encrypt_rsa_with_pubkey(our_pubkey, aes_key)
            enc_key_recipient = CryptoManager.encrypt_rsa_with_pubkey(target_pubkey, aes_key)

            # Отправляем запрос на сервер для создания секретного чата
            await self.network.send({
                "action": "create_secret_chat",
                "target": target_username,
                "encrypted_key_sender": enc_key_sender,
                "encrypted_key_recipient": enc_key_recipient
            })
        except Exception as e:
            logger.error(f"Failed to create secret chat: {e}", exc_info=True)
            self.show_snackbar("Ошибка создания секретного чата", ft.Colors.RED)

    def handle_open_profile(self):
        if not self.active_chat_id: return
        # Запрашиваем у сервера список участников группы
        self.page.run_task(self.network.send, {"action": "get_chat_members", "chat_id": self.active_chat_id})

    def update_chat_header(self):
        """Умное обновление шапки чата (имени, статуса и 'печатает...')"""
        if not hasattr(self, 'chat_screen'): return

        chat_data = self.chats_info.get(self.active_chat_id, {})
        if not chat_data: return

        cname = self.get_chat_name(chat_data)
        is_group = chat_data.get('type') == 'group'

        subtitle = ""
        is_online = False

        # --- ЛОГИКА ТАЙПИНГА ---
        now = time.time()
        # Очищаем тех, кто уже перестал печатать (время вышло)
        active_typings = {}
        if self.active_chat_id in self.typing_timers:
            active_typings = {u: t for u, t in self.typing_timers[self.active_chat_id].items() if t > now}
            self.typing_timers[self.active_chat_id] = active_typings

        typing_users = list(active_typings.keys())

        # Если кто-то печатает — это ПРИОРИТЕТ над обычным статусом "в сети"
        if typing_users:
            is_online = True  # Надпись будет зеленого цвета
            if len(typing_users) == 1:
                subtitle = f"{typing_users[0]} печатает..." if is_group else "печатает..."
            else:
                subtitle = f"{len(typing_users)} чел. печатают..."

        # Если никто не печатает, показываем стандартный статус
        else:
            if chat_data.get('type') == 'dialog':
                users = chat_data.get('name', '').split('_')
                if len(users) == 2:
                    other_user = users[0] if users[1] == self.current_username else users[1]
                    status = self.users_status.get(other_user, {})
                    if status.get("is_online"):
                        subtitle = "в сети"
                        is_online = True
                    elif status.get("last_seen"):
                        ts = datetime.fromtimestamp(status["last_seen"]).strftime('%H:%M')
                        subtitle = f"был(а) {ts}"
                    else:
                        subtitle = "оффлайн"
            elif is_group:
                subtitle = "групповой чат"

        # Применяем к UI
        self.chat_screen.set_chat_title(cname, subtitle=subtitle, show_info=True, is_online=is_online)

    def show_create_group_modal(self):
        def on_create(name):
            self.page.run_task(self.network.send, {"action": "create_group", "name": name})

        CreateGroupDialog(self.page, on_create).show()

    def show_add_member_modal(self):
        def on_add(username):
            self.page.run_task(self.network.send,
                               {"action": "add_member", "chat_id": self.active_chat_id, "username": username})

        dialog = AddMemberDialog(self.page, on_add, self.handle_search_users)
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

        async def on_load_sessions():
            return await self.network.get_sessions()

        async def on_terminate_sessions():
            success, msg = await self.network.terminate_other_sessions()
            if success:
                self.show_snackbar("Другие сеансы успешно завершены")
                return True, ""
            else:
                self.show_snackbar(f"Ошибка: {msg}")
                return False, msg

        dialog = SettingsDialog(
            self.page,
            self.settings,
            on_settings_changed,
            on_logout,
            on_load_sessions,
            on_terminate_sessions
        )
        dialog.show()

    def get_media_url(self, msg_id: int) -> str:
        """Генерирует прямую ссылку на скачивание файла с вшитым токеном"""
        return f"{self.network.api_url}/messages/files/{msg_id}?token={self.network.token}"

    def show_media_modal(self, media_url: str, is_video: bool, filename: str):
        """Открывает окно просмотра медиа с зумом или плеером"""
        dialog = MediaDialog(self.page, media_url, is_video, filename)
        dialog.show()

    # ==========================================
    #       РАБОТА С ФАЙЛАМИ
    # ==========================================
    def handle_attach_file(self):
        if not self.active_chat_id: return
        async def pick_task():
            try:
                files = await ft.FilePicker().pick_files(allow_multiple=False)
                if not files: return
                f = files[0]

                import os
                if f.path and os.path.isdir(f.path):
                    self.show_snackbar("Ошибка: Выбранный объект является папкой!")
                    return

                if self.editing_msg_id is not None:
                    self.editing_new_file = f.path
                    self.editing_new_filename = f.name
                    self.editing_delete_file = False
                    
                    label_val = self.chat_screen.edit_label.value
                    if " | 📎" in label_val:
                        label_val = label_val.split(" | 📎")[0]
                    elif " (файл удален)" in label_val:
                        label_val = label_val.replace(" (файл удален)", "")
                    
                    self.chat_screen.edit_label.value = label_val + f" | 📎 -> {f.name}"
                    self.chat_screen.delete_attached_file_btn.visible = True
                    self.chat_screen.edit_panel.update()
                    self.show_snackbar(f"Файл {f.name} выбран для замены!")
                else:
                    self.show_snackbar(f"Отправка файла {f.name}...")
                    await self.network.send({
                        "action": "send_file",
                        "chat_id": self.active_chat_id,
                        "filename": f.name,
                        "filepath": f.path
                    })
            except Exception as ex:
                self.show_snackbar("Ошибка при чтении файла!")

        self.page.run_task(pick_task)

    def handle_download_file(self, msg_id, filename):
        async def download_task():
            try:
                path = await ft.FilePicker().save_file(file_name=filename)
                if path:
                    self.show_snackbar("Скачивание файла...")
                    # Передаем путь сохранения прямо в сеть!
                    await self.network.send({
                        "action": "req_file",
                        "msg_id": msg_id,
                        "save_path": path  # <--- ВОТ ТУТ
                    })
            except Exception as e:
                self.show_snackbar("Ошибка сохранения файла!")
        self.page.run_task(download_task)

    def handle_delete_message(self, msg_id):
        if not self.active_chat_id: return
        if not self.network.ws:
            self.show_snackbar("Нет подключения к сети!")
            return
        self.page.run_task(self.network.send,
                           {"action": "delete_msg", "chat_id": self.active_chat_id, "msg_id": msg_id})

    def handle_edit_message(self, msg_id, text, file_name):
        self.editing_msg_id = msg_id
        self.editing_delete_file = False
        self.editing_new_file = None
        self.chat_screen.start_edit_mode(text, file_name)

    def handle_cancel_edit(self):
        self.editing_msg_id = None
        self.editing_delete_file = False
        self.editing_new_file = None
        self.chat_screen.stop_edit_mode()

    def handle_delete_attached_file(self):
        self.editing_delete_file = True
        self.editing_new_file = None
        self.editing_new_filename = None
        self.chat_screen.delete_attached_file_btn.visible = False
        
        label_val = self.chat_screen.edit_label.value
        if " | 📎" in label_val:
            label_val = label_val.split(" | 📎")[0]
        label_val += " (файл удален)"
        self.chat_screen.edit_label.value = label_val
        try:
            self.chat_screen.edit_panel.update()
        except Exception:
            pass

    async def handle_search_users(self, query: str) -> list:
        return await self.network.search_users(query)

    def handle_search_messages(self, query: str):
        if not self.active_chat_id: return
        chat_data = self.chats_info.get(self.active_chat_id, {})
        if chat_data.get("type") == "secret":
            results = self.db.search_messages(self.active_chat_id, query)
            self.chat_screen.clear_messages()
            self.is_searching = True
            self.show_snackbar(f"Найдено: {len(results)} сообщений")
            for msg in results:
                self.chat_screen.add_message(
                    sender=msg['sender'],
                    text=msg.get('text', ''),
                    timestamp=msg['timestamp'],
                    msg_id=msg.get('id'),
                    file_name=msg.get('file_name'),
                    local_path=msg.get('local_path'),
                    updated_at=msg.get('updated_at'),
                    is_read=msg.get('is_read', False)
                )
        else:
            self.page.run_task(self.network.send, {
                "action": "search_messages",
                "chat_id": self.active_chat_id,
                "query": query
            })

    def handle_clear_search(self):
        self.is_searching = False
        if not self.active_chat_id: return
        self.history_offset = 0
        self.is_loading_history = True
        self.has_more_history = True
        self.page.run_task(self.network.send, {
            "action": "get_history",
            "chat_id": self.active_chat_id,
            "limit": 20,
            "offset": 0
        })

    # ==========================================
    #       СЕТЕВЫЕ СОБЫТИЯ
    # ==========================================

    async def on_net_disconnect(self):
        # Если юзер сам нажал "Выйти", переподключаться не надо
        if not getattr(self, 'is_logged_in', False):
            return

        if getattr(self, 'is_reconnecting', False):
            return
        self.is_reconnecting = True

        if hasattr(self, 'chat_screen'):
            self.chat_screen.add_system_message("Связь потеряна. Переподключение через 3 сек...", ft.Colors.RED)

        self.page.title = f"Simple Messenger ({self.current_username}) [Offline]"
        self.page.update()

        try:
            await asyncio.sleep(3)

            # Пытаемся переподключиться тихо (в фоне)
            response = await self.network.connect(
                self.settings.get("host"), int(self.settings.get("port", 8888)),
                self.settings.get("username"),
                self.settings.get("password")
            )

            if response.get("status") == "ok":
                self.chat_screen.add_system_message("Соединение восстановлено!", ft.Colors.GREEN)
                self.page.title = f"Simple Messenger ({self.current_username})"
                self.page.update()
                await self.network.send({"action": "get_chats"})
                if self.active_chat_id:
                    await self.network.send({"action": "get_history", "chat_id": self.active_chat_id, "limit": 20})
                self.page.run_task(self.network.listen)
                self.is_reconnecting = False
            else:
                self.is_reconnecting = False
                # Если сервер все еще лежит - пробуем снова
                self.page.run_task(self.on_net_disconnect)
        except Exception as e:
            self.is_reconnecting = False
            self.page.run_task(self.on_net_disconnect)

    def decrypt_message_in_place(self, chat_id, msg):
        if not msg or not chat_id:
            return
        chat_data = self.chats_info.get(chat_id)
        if chat_data and chat_data.get("type") == "secret":
            sym_key_b64 = chat_data.get("symmetric_key")
            if sym_key_b64 and msg.get("text"):
                try:
                    key_bytes = base64.b64decode(sym_key_b64)
                    decrypted_text = CryptoManager.decrypt_aes(key_bytes, msg["text"])
                    msg["text"] = decrypted_text
                except Exception as e:
                    logger.error(f"Failed to decrypt message {msg.get('id')}: {e}")
                    msg["text"] = "[Ошибка расшифрования]"

    async def on_net_message(self, data):
        action = data.get("action")

        if action == "new_msg":
            chat_id, msg = data.get("chat_id"), data.get("message")
            if chat_id and msg:
                self.decrypt_message_in_place(chat_id, msg)
                self.db.save_messages(chat_id, [msg])

            chat_data = self.chats_info.get(chat_id, {})
            cname = self.get_chat_name(chat_data) if chat_data else f"ID:{chat_id}"

            is_active_chat = (chat_id == self.active_chat_id)
            is_hidden = getattr(self.page.window, "minimized", False) or not getattr(self.page.window, "visible", True)

            if is_active_chat:
                local_path = None
                m_id = msg.get('id')
                if m_id:
                    with self.db._get_conn() as conn:
                        cursor = conn.execute("SELECT local_path FROM messages WHERE id = ?", (m_id,))
                        row = cursor.fetchone()
                        if row:
                            local_path = row['local_path']

                self.chat_screen.add_message(
                    sender=msg['sender'],
                    text=msg.get('text', ''),
                    timestamp=msg['timestamp'],
                    msg_id=msg.get('id'),
                    file_name=msg.get('file_name'),
                    local_path=local_path,
                    updated_at=msg.get('updated_at'),
                    is_read=msg.get('is_read', False)
                )
                if msg['sender'] != self.current_username:
                    self.page.run_task(self.network.send, {"action": "read_chat", "chat_id": chat_id})
            else:
                self.chat_screen.add_system_message(f"[🔔] Новое сообщение в чате '{cname}'", ft.Colors.YELLOW)

            if msg['sender'] != self.current_username:
                if is_hidden or not is_active_chat or self.settings.get("notify_always"):
                    notif_text = f"Отправил файл: {msg.get('file_name')}" if msg.get(
                        'file_name') else f"{msg['sender']}: {msg.get('text', '')}"
                    self.os.notify(f"Чат: {cname}", notif_text)
                    self.os.set_tray_badge(True)

        elif action == "msg_deleted":
            msg_id = data.get("msg_id")
            if msg_id:
                self.db.delete_message(msg_id)
            if data.get("chat_id") == self.active_chat_id:
                self.chat_screen.remove_message(msg_id)

        elif action == "msg_edited":
            msg = data.get("message")
            chat_id = data.get("chat_id")
            if chat_id and msg:
                self.decrypt_message_in_place(chat_id, msg)
            if msg:
                self.db.update_message(
                    msg_id=msg['id'],
                    text=msg.get('text', ''),
                    file_name=msg.get('file_name'),
                    updated_at=msg.get('updated_at'),
                    is_read=msg.get('is_read', False)
                )
            if data.get("chat_id") == self.active_chat_id and msg:
                self.chat_screen.update_message(
                    msg_id=msg['id'],
                    sender=msg['sender'],
                    text=msg.get('text', ''),
                    timestamp=msg['timestamp'],
                    file_name=msg.get('file_name'),
                    updated_at=msg.get('updated_at'),
                    is_read=msg.get('is_read', False)
                )

        elif action == "search_results":
            chat_id = data.get("chat_id")
            if chat_id == self.active_chat_id:
                messages = data.get("messages", [])
                self.chat_screen.clear_messages()
                self.is_searching = True
                
                self.show_snackbar(f"Найдено: {len(messages)} сообщений")
                
                for msg in messages:
                    local_path = None
                    m_id = msg.get('id')
                    if m_id:
                        with self.db._get_conn() as conn:
                            cursor = conn.execute("SELECT local_path FROM messages WHERE id = ?", (m_id,))
                            row = cursor.fetchone()
                            if row:
                                local_path = row['local_path']

                    self.chat_screen.add_message(
                        sender=msg['sender'],
                        text=msg.get('text', ''),
                        timestamp=msg['timestamp'],
                        msg_id=msg.get('id'),
                        file_name=msg.get('file_name'),
                        local_path=local_path,
                        updated_at=msg.get('updated_at'),
                        is_read=msg.get('is_read', False)
                    )

        elif action == "messages_read":
            chat_id = data.get("chat_id")
            if chat_id:
                self.db.mark_chat_as_read(chat_id, self.current_username)
            if chat_id == self.active_chat_id:
                self.chat_screen.mark_own_messages_as_read()

        elif action == "chat_list":
            chats = data.get("chats", [])
            try:
                self.crypto_mgr.init_keys()
            except Exception:
                pass
            for c in chats:
                if c.get("type") == "secret" and c.get("encrypted_key"):
                    try:
                        dec_key_bytes = self.crypto_mgr.decrypt_rsa(c["encrypted_key"])
                        c["symmetric_key"] = base64.b64encode(dec_key_bytes).decode("utf-8")
                    except Exception as e:
                        logger.error(f"Failed to decrypt symmetric key for chat {c.get('id')}: {e}", exc_info=True)
            self.db.save_chats(chats)
            
            # Читаем чаты обратно из БД, чтобы получить полностью объединенные записи
            db_chats = self.db.get_chats()
            for c in db_chats:
                self.chats_info[c['id']] = c
            self.update_drawer()

            # Если есть отложенный переход на новый чат
            pending_id = getattr(self, 'pending_active_chat_id', None)
            if pending_id and pending_id in self.chats_info:
                self.pending_active_chat_id = None
                self.handle_select_chat(pending_id)
            elif self.active_chat_id not in self.chats_info:
                if chats:
                    # Ищем сначала Избранное
                    saved_chat = next((c for c in chats if c.get('type') == 'saved'), None)
                    target_chat = saved_chat if saved_chat else chats[0]
                    self.handle_select_chat(target_chat['id'])
            else:
                self.update_chat_header()

        elif action in ["group_created", "dialog_created"]:
            # Сохраняем ID созданного чата, чтобы переключиться на него при обновлении списка
            self.pending_active_chat_id = data.get("chat_id")
            self.page.run_task(self.network.send, {"action": "get_chats"})

        elif action in ["chat_added", "member_added"]:
            # Обновляем список чатов, если нас добавили
            self.page.run_task(self.network.send, {"action": "get_chats"})
            if action == "member_added":
                self.show_snackbar("Участник успешно добавлен!")

        elif action == "history":
            messages = data.get("messages", [])
            chat_id = data.get("chat_id")
            offset = data.get("offset", 0)  # Читаем сдвиг, который мы же и отправили!

            if chat_id and messages:
                for msg in messages:
                    self.decrypt_message_in_place(chat_id, msg)
                self.db.save_messages(chat_id, messages)

            # Если сервер прислал меньше 20 сообщений, значит мы дошли до самого начала истории
            if len(messages) < 20:
                self.has_more_history = False

            # Пытаемся загрузить данные из локального кэша, чтобы получить local_path
            enriched_msgs = []
            if chat_id:
                enriched_msgs = self.db.get_messages(chat_id, limit=20, offset=offset)

            if offset == 0:
                # Первая страница
                self.chat_screen.clear_messages()
                self.update_chat_header()
                for msg in enriched_msgs:
                    self.chat_screen.add_message(
                        sender=msg['sender'], text=msg.get('text', ''),
                        timestamp=msg['timestamp'], msg_id=msg.get('id'), file_name=msg.get('file_name'),
                        local_path=msg.get('local_path'),
                        updated_at=msg.get('updated_at'), is_read=msg.get('is_read', False)
                    )
            else:
                # Подгрузка СТАРЫХ сообщений
                if enriched_msgs:
                    self.chat_screen.prepend_messages(enriched_msgs)
            self.is_loading_history = False  # Снимаем блокировку, можно крутить дальше

        elif action == "history_error":
            chat_id = data.get("chat_id")
            offset = data.get("offset", 0)
            if chat_id == self.active_chat_id:
                # Пытаемся загрузить данные из локального кэша
                cached_msgs = self.db.get_messages(chat_id, limit=20, offset=offset)
                if not cached_msgs:
                    self.has_more_history = False
                else:
                    if offset == 0:
                        self.chat_screen.clear_messages()
                        self.update_chat_header()
                        for msg in cached_msgs:
                            self.chat_screen.add_message(
                                sender=msg['sender'], text=msg.get('text', ''),
                                timestamp=msg['timestamp'], msg_id=msg.get('id'), file_name=msg.get('file_name'),
                                local_path=msg.get('local_path'),
                                updated_at=msg.get('updated_at'), is_read=msg.get('is_read', False)
                            )
                    else:
                        self.chat_screen.prepend_messages(cached_msgs)
                self.is_loading_history = False

        elif action == "status":
            # Сервер прислал чей-то статус
            username = data.get("username")
            self.users_status[username] = {
                "is_online": data.get("status") == "online",
                "last_seen": data.get("last_seen")
            }
            # Сразу перерисовываем шапку
            self.update_chat_header()

        elif action == "typing":
            chat_id = data.get("chat_id")
            typing_user = data.get("username")

            if chat_id not in self.typing_timers:
                self.typing_timers[chat_id] = {}

            # Устанавливаем, что надпись будет висеть ровно 3 секунды
            self.typing_timers[chat_id][typing_user] = time.time() + 3.0

            if chat_id == self.active_chat_id:
                self.update_chat_header()

            async def clear_typing():
                await asyncio.sleep(3.1)
                if self.active_chat_id == chat_id:
                    self.update_chat_header()

            self.page.run_task(clear_typing)

        elif action == "chat_members_data":
            chat_data = self.chats_info.get(self.active_chat_id, {})
            cname = self.get_chat_name(chat_data)
            ctype = chat_data.get("type", "group")
            members = data.get("members", [])

            # Извлекаем файлы и ссылки из локальной БД
            files = self.db.get_chat_files(self.active_chat_id)
            links = self.db.get_chat_links(self.active_chat_id)

            def handle_open_media_from_info(msg_id, is_vid, name):
                media_url = self.get_media_url(msg_id)
                self.show_media_modal(media_url, is_vid, name)

            self.profile_dialog = ChatProfileDialog(
                self.page,
                cname,
                ctype,
                members,
                files,
                links,
                self.show_add_member_modal,
                self.handle_download_file,
                handle_open_media_from_info
            )
            self.profile_dialog.show()

        elif action == "file_saved":
            filepath = data.get("filepath")
            msg_id = data.get("msg_id")
            if filepath:
                if msg_id:
                    self.db.update_message_local_path(msg_id, filepath)
                    # Update local path in the profile dialog if open
                    if hasattr(self, 'profile_dialog') and self.profile_dialog and getattr(self.profile_dialog, 'dialog', None) and self.profile_dialog.dialog.open:
                        self.profile_dialog.update_file_local_path(msg_id, filepath)
                    # Smoothly update message in UI if it's currently displayed
                    if hasattr(self, 'chat_screen') and self.chat_screen:
                        for ctrl in self.chat_screen.chat_history.controls:
                            if getattr(ctrl, "msg_id", None) == msg_id:
                                sender = getattr(ctrl, "sender", "")
                                text = getattr(ctrl, "text", "")
                                timestamp = getattr(ctrl, "timestamp", 0)
                                file_name = getattr(ctrl, "file_name", None)
                                updated_at = getattr(ctrl, "updated_at", None)
                                is_read = getattr(ctrl, "is_read", False)
                                self.chat_screen.update_message(
                                    msg_id, sender, text, timestamp, file_name, updated_at, is_read, filepath
                                )
                                break

                def on_show_in_finder(e, path=filepath):
                    import subprocess
                    import platform
                    try:
                        system = platform.system()
                        if system == "Darwin":
                            subprocess.run(["open", "-R", path])
                        elif system == "Windows":
                            subprocess.run(["explorer", "/select,", os.path.normpath(path)])
                        else:
                            subprocess.run(["xdg-open", os.path.dirname(path)])
                    except Exception as err:
                        logger.error(f"Failed to open in finder: {err}")

                import platform
                action_label = "Показать в Finder" if platform.system() == "Darwin" else "Показать в папке"

                # Системное уведомление macOS/Windows
                self.os.notify("Файл скачан!", f"Сохранен в: {filepath}")

                snack = ft.SnackBar(
                    content=ft.Text("Файл успешно скачан!"),
                    action=ft.SnackBarAction(
                        label=action_label,
                        on_click=on_show_in_finder
                    ),
                    duration=5000
                )
                self.page.overlay.append(snack)
                snack.open = True
                self.page.update()

    def update_drawer(self):
        # Функция для кнопки закрытия
        def _close_drawer_btn(e):
            async def close_task():
                if self.page.drawer:
                    await self.page.close_drawer()
            self.page.run_task(close_task)

        controls = [
            ft.Container(
                padding=10,
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

        # Добавляем избранное на самый верх
        if saved_id:
            controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.BOOKMARK, color=ft.Colors.BLUE_400),
                    title=ft.Text("Избранное", weight="bold"),
                    on_click=make_select(saved_id)
                )
            )
            controls.append(ft.Divider())

        # --- 1. Групповые чаты ---
        has_groups = False
        for cid, chat in self.chats_info.items():
            if chat.get('type') == 'group':
                has_groups = True
                controls.append(
                    ft.ListTile(leading=ft.Icon(ft.Icons.GROUP),
                    title=ft.Text(chat['name']),
                    on_click=make_select(cid)))
        if not has_groups:
            controls.append(ft.Container(padding=15, content=ft.Text("Нет групп", color=ft.Colors.GREY_500)))
        controls.append(ft.Divider())

        # --- 2. Личные диалоги ---
        has_dialogs = False
        for cid, chat in self.chats_info.items():
            ctype = chat.get('type')
            if ctype in ['dialog', 'secret']:
                has_dialogs = True
                display_name = self.get_chat_name(chat)
                if ctype == 'secret':
                    leading_icon = ft.Icon(ft.Icons.LOCK, color=ft.Colors.GREEN)
                else:
                    leading_icon = ft.Icon(ft.Icons.PERSON)
                controls.append(
                    ft.ListTile(
                        leading=leading_icon,
                        title=ft.Text(display_name),
                        on_click=make_select(cid)
                    )
                )

        if not has_dialogs:
            controls.append(ft.Container(padding=15, content=ft.Text("Нет личных сообщений", color=ft.Colors.GREY_500)))
        controls.append(ft.Divider())

        # --- 3. Настройки ---
        controls.append(
            ft.ListTile(leading=ft.Icon(ft.Icons.ADD),
            title=ft.Text("Создать диалог"),
            on_click=lambda e: self.show_pm_modal()))
        controls.append(
            ft.ListTile(leading=ft.Icon(ft.Icons.GROUP_ADD),
            title=ft.Text("Создать группу"),
            on_click=lambda e: self.show_create_group_modal()))
        controls.append(ft.Divider())
        controls.append(
            ft.ListTile(leading=ft.Icon(ft.Icons.SETTINGS),
            title=ft.Text("Настройки"),
            on_click=lambda e: self.show_settings_modal()))

        if not self.page.drawer:
            self.page.drawer = ft.NavigationDrawer(controls=controls)
        else:
            self.page.drawer.controls = controls

        self.page.update()

    def handle_select_chat(self, chat_id):
        if self.page.drawer:
            async def close_drawer_task():
                await self.page.close_drawer()
            self.page.run_task(close_drawer_task)

        self.active_chat_id = chat_id
        self.os.set_tray_badge(False)

        self.history_offset = 0
        self.is_loading_history = True  # Блокируем скролл, пока не придет первая пачка от сети
        self.has_more_history = True

        self.update_chat_header()  # Обновляем заголовок чата сразу

        if hasattr(self, 'chat_screen') and self.chat_screen:
            self.chat_screen.clear_messages()
            # Загружаем мгновенно из локального кэша
            cached_msgs = self.db.get_messages(chat_id, limit=20, offset=0)
            for msg in cached_msgs:
                self.chat_screen.add_message(
                    sender=msg['sender'], text=msg.get('text', ''),
                    timestamp=msg['timestamp'], msg_id=msg.get('id'), file_name=msg.get('file_name'),
                    local_path=msg.get('local_path'),
                    updated_at=msg.get('updated_at'), is_read=msg.get('is_read', False)
                )

        self.page.run_task(self.network.send, {"action": "get_history", "chat_id": chat_id, "limit": 20, "offset": 0})

    def handle_load_more_history(self):
        # Если мы в режиме поиска, мы не подгружаем историю
        if self.is_searching:
            return
        # Если мы уже грузим историю или её больше нет — ничего не делаем
        if self.is_loading_history or not self.has_more_history:
            return

        self.is_loading_history = True
        self.history_offset += 20

        if not self.network.ws:
            # Офлайн режим: загружаем из локальной БД напрямую
            cached_msgs = self.db.get_messages(self.active_chat_id, limit=20, offset=self.history_offset)
            if not cached_msgs:
                self.has_more_history = False
            else:
                self.chat_screen.prepend_messages(cached_msgs)
            self.is_loading_history = False
            return

        # Просим сервер прислать старые сообщения
        self.page.run_task(self.network.send, {
            "action": "get_history",
            "chat_id": self.active_chat_id,
            "limit": 20,
            "offset": self.history_offset
        })