import logging
import flet as ft
from ui.controllers.base import BaseController
from ui.screens.login_screen import LoginScreen
from ui.dialogs.register_dialog import RegisterDialog
from ui.dialogs.restore_dialog import RestoreDialog
from database import ClientDatabase
from system.crypto import CryptoManager

logger = logging.getLogger("messenger.auth_controller")


class AuthController(BaseController):
    def __init__(self, page: ft.Page, app_controller):
        super().__init__(page, app_controller)
        self.login_screen = None

    def show_login(self):
        self.page.clean()
        self.page.drawer = None

        self.login_screen = LoginScreen(
            settings=self.app.settings,
            on_login_callback=self.handle_login,
            on_show_register_callback=self.show_register_modal,
            on_show_restore_callback=self.show_restore_modal
        )
        self.page.add(self.login_screen)

    def handle_login(self, host, port, username, password, auto_login):
        import re
        if not re.match(r"^[a-z]+\.[a-z]{2}$", username):
            if self.login_screen:
                self.login_screen.show_error("Логин должен быть в формате фамилия.ио (в нижнем регистре), например: ivanov.dn")
            return

        async def login_task():
            response = await self.app.network.connect(host, int(port), username, password)

            if response.get("status") != "ok":
                # Если сервер недоступен, но у нас включен автологин, заходим в оффлайн-режиме
                if response.get("msg") == "Сервер недоступен" and auto_login:
                    self.app.current_username = username
                    self.app.current_password = password
                    self.app.db = ClientDatabase(self.app.settings_manager.APP_DIR / f"client_cache_{username}.sqlite")
                    self.app.crypto_mgr = CryptoManager(self.app.settings_manager.APP_DIR / f"keys_{username}", username)
                    self.app.page.title = f"Simple Messenger ({self.app.current_username}) [Offline]"
                    self.app.show_chat_screen()
                    self.page.run_task(self.app.on_net_disconnect)
                    return

                if self.login_screen:
                    self.login_screen.show_error(f"Ошибка: {response.get('msg')}")
                return

            self.app.current_username = username
            self.app.current_password = password
            self.app.db = ClientDatabase(self.app.settings_manager.APP_DIR / f"client_cache_{username}.sqlite")
            self.app.crypto_mgr = CryptoManager(self.app.settings_manager.APP_DIR / f"keys_{username}", username)
            
            self.app.settings.update({
                "host": host,
                "port": port,
                "username": username,
                "password": password if auto_login else "",
                "auto_login": auto_login
            })
            self.app.settings_manager.save_settings(self.app.settings)

            self.app.page.title = f"Simple Messenger ({self.app.current_username})"
            self.app.show_chat_screen()

            # Инициализация и загрузка публичного ключа для E2EE
            try:
                self.app.crypto_mgr.init_keys()
                pubkey = self.app.crypto_mgr.get_public_key_pem()
                await self.app.network.upload_public_key(pubkey)
            except Exception as e:
                logger.error(f"Failed to upload E2EE public key: {e}", exc_info=True)

            await self.app.network.send({"action": "get_chats"})
            self.page.run_task(self.app.network.listen)

        self.page.run_task(login_task)

    def show_register_modal(self):
        if not self.login_screen:
            return
        current_host = self.login_screen.host_input.value.strip()
        current_port = self.login_screen.port_input.value.strip()

        async def on_register(host, port, username, password, secret):
            response = await self.app.network.connect(host, port, username, password, mode="register", secret=secret)
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
        if not self.login_screen:
            return
        current_host = self.login_screen.host_input.value.strip()
        current_port = self.login_screen.port_input.value.strip() or "8888"

        async def on_restore(host, port, username, password, secret):
            response = await self.app.network.connect(host, int(port), username, password, mode="reset", secret=secret)
            if response.get("status") != "ok":
                return False, response.get('msg', 'Неизвестная ошибка')

            # Успешно сбросили! Подставляем новые данные в форму входа
            self.login_screen.host_input.value = host
            self.login_screen.port_input.value = port
            self.login_screen.user_input.value = username
            self.login_screen.pass_input.value = password
            self.page.update()

            self.app.show_snackbar("Пароль изменен! Выполняется вход...", ft.Colors.GREEN)

            # Сразу логинимся с новым паролем
            self.handle_login(host, port, username, password, self.login_screen.auto_login_checkbox.value)
            return True, ""

        dialog = RestoreDialog(self.page, current_host, current_port, on_restore)
        dialog.show()
