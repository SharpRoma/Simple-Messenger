import flet as ft
from .base_dialog import BaseDialog


class RegisterDialog(BaseDialog):
    # Добавили default_port
    def __init__(self, page: ft.Page, default_host: str, default_port: str, on_register):
        super().__init__(page)
        self.on_register = on_register

        self.reg_host = ft.TextField(
            label="IP сервера", value=default_host, expand=True, autofocus=not bool(default_host),
            input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9\.]", replacement_string="")
        )
        self.reg_port = ft.TextField(
            label="Порт", value=default_port, width=80,
            input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string="")
        )

        server_row = ft.Row([self.reg_host, self.reg_port])  # <--- Ряд сервера

        self.reg_user = ft.TextField(label="Придумайте логин", autofocus=bool(default_host))
        self.reg_pass = ft.TextField(label="Придумайте пароль")
        self.reg_secret = ft.TextField(
            label="Секретный код сервера", password=True, can_reveal_password=True,
            on_submit=self._handle_submit
        )
        self.reg_err = ft.Text(color="red")

        self.dialog = ft.AlertDialog(
            title=ft.Text("Регистрация аккаунта"),
            # Заменили отдельный reg_host на server_row
            content=ft.Column([server_row, self.reg_user, self.reg_pass, self.reg_secret, self.reg_err], tight=True),
            actions=[
                ft.TextButton("Зарегистрироваться", on_click=self._handle_submit),
                ft.TextButton("Отмена", on_click=lambda e: self.close())
            ]
        )

    async def _handle_submit(self, e):
        host = self.reg_host.value.strip()
        port = self.reg_port.value.strip()  # <--- Читаем порт
        username = self.reg_user.value.strip()
        password = self.reg_pass.value.strip()
        secret = self.reg_secret.value.strip()

        if not host or not port or not username or not password or not secret:
            self.reg_err.value = "Заполните все поля!"
            self.reg_err.color = ft.Colors.RED
            self.page.update()
            return

        import re
        if not re.match(r"^[a-zа-яё]+\.[a-zа-яё]{2}$", username):
            self.reg_err.value = "Логин должен быть в формате фамилия.ио (в нижнем регистре), например: ivanov.dn"
            self.reg_err.color = ft.Colors.RED
            self.page.update()
            return

        self.reg_err.value = "Подключение..."
        self.reg_err.color = ft.Colors.BLUE
        self.page.update()

        # Передаем порт
        success, error_msg = await self.on_register(host, port, username, password, secret)

        if success:
            self.close()
        else:
            self.reg_err.value = error_msg
            self.reg_err.color = ft.Colors.RED
            self.page.update()