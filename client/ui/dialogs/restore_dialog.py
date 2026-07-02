import flet as ft
from .base_dialog import BaseDialog


class RestoreDialog(BaseDialog):
    def __init__(self, page: ft.Page, default_host: str, default_port: str, on_restore):
        super().__init__(page)
        self.on_restore = on_restore

        self.reg_host = ft.TextField(
            label="IP сервера", value=default_host, expand=True, autofocus=not bool(default_host),
            input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9\.]", replacement_string="")
        )
        self.reg_port = ft.TextField(
            label="Порт", value=default_port, width=80,
            input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string="")
        )
        server_row = ft.Row([self.reg_host, self.reg_port])

        self.reg_user = ft.TextField(label="Логин пользователя", autofocus=bool(default_host))
        self.reg_secret = ft.TextField(label="Секретный код сервера", password=True, can_reveal_password=True)
        self.reg_pass = ft.TextField(label="Новый пароль", password=True, can_reveal_password=True,
                                     on_submit=self._handle_submit)

        self.reg_err = ft.Text(color="red", text_align=ft.TextAlign.CENTER, width=300)

        self.dialog = ft.AlertDialog(
            title=ft.Text("Восстановление пароля"),
            content=ft.Column([server_row, self.reg_user, self.reg_secret, self.reg_pass, self.reg_err], tight=True),
            actions=[
                ft.TextButton("Сбросить пароль", on_click=self._handle_submit),
                ft.TextButton("Отмена", on_click=lambda e: self.close())
            ]
        )

    async def _handle_submit(self, e):
        host = self.reg_host.value.strip()
        port = self.reg_port.value.strip()
        username = self.reg_user.value.strip()
        secret = self.reg_secret.value.strip()
        password = self.reg_pass.value.strip()

        if not host or not port or not username or not password or not secret:
            self.reg_err.value = "Заполните все поля!"
            self.reg_err.color = ft.Colors.RED
            self.page.update()
            return

        self.reg_err.value = "Проверка..."
        self.reg_err.color = ft.Colors.BLUE
        self.page.update()

        success, error_msg = await self.on_restore(host, port, username, password, secret)
        if success:
            self.close()
        else:
            self.reg_err.value = error_msg
            self.reg_err.color = ft.Colors.RED
            self.page.update()