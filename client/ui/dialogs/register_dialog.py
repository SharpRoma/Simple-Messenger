import flet as ft
from .base_dialog import BaseDialog

class RegisterDialog(BaseDialog):
    def __init__(self, page: ft.Page, default_host: str, on_register):
        super().__init__(page)
        self.on_register = on_register

        # Если хост пустой, фокус будет на нем. Иначе на логине.
        self.reg_host = ft.TextField(
            label="IP сервера",
            value=default_host,
            autofocus=not bool(default_host),
            input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9\.]", replacement_string="")
        )
        self.reg_user = ft.TextField(label="Придумайте логин", autofocus=bool(default_host))
        self.reg_pass = ft.TextField(label="Придумайте пароль")
        self.reg_secret = ft.TextField(label="Секретный код сервера", on_submit=self._handle_submit)
        self.reg_err = ft.Text(color="red")

        self.dialog = ft.AlertDialog(
            title=ft.Text("Регистрация аккаунта"),
            content=ft.Column([self.reg_host, self.reg_user, self.reg_pass, self.reg_secret, self.reg_err], tight=True),
            actions=[
                ft.TextButton("Зарегистрироваться", on_click=self._handle_submit),
                ft.TextButton("Отмена", on_click=lambda e: self.close())
            ]
        )

    async def _handle_submit(self, e):
        host = self.reg_host.value.strip()
        username = self.reg_user.value.strip()
        password = self.reg_pass.value.strip()
        secret = self.reg_secret.value.strip()

        if not host or not username or not password or not secret:
            self.reg_err.value = "Заполните все поля!"
            self.reg_err.color = ft.Colors.RED
            self.page.update()
            return

        self.reg_err.value = "Подключение..."
        self.reg_err.color = ft.Colors.BLUE
        self.page.update()

        success, error_msg = await self.on_register(host, username, password, secret)

        if success:
            self.close()
        else:
            self.reg_err.value = error_msg
            self.reg_err.color = ft.Colors.RED
            self.page.update()