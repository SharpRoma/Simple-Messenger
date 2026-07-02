import flet as ft


class LoginScreen(ft.Container):
    def __init__(self, settings: dict, on_login_callback, on_show_register_callback, on_show_restore_callback):
        super().__init__()
        self.settings = settings

        # Коллбэки
        self.on_login_callback = on_login_callback
        self.on_show_register_callback = on_show_register_callback
        self.on_show_restore_callback = on_show_restore_callback

        # Настройки самого контейнера, чтобы он занял весь экран и был по центру
        self.expand = True
        self.alignment = ft.Alignment.CENTER

        # Инициализируем элементы интерфейса
        self._build_ui()

    def _build_ui(self):
        # 1. Поле хоста (теперь оно expand=True, чтобы занять всё доступное место)
        self.host_input = ft.TextField(
            label="Хост сервера",
            value=self.settings.get("host"),
            expand=True
        )

        # 2. НОВОЕ Поле порта (только цифры)
        self.port_input = ft.TextField(
            label="Порт",
            value=str(self.settings.get("port", "8888")),
            width=80,
            input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string="")
        )

        # 3. Объединяем их в один ряд шириной 300
        server_row = ft.Row([self.host_input, self.port_input], width=300)

        self.user_input = ft.TextField(
            label="Логин", value=self.settings.get("username"), width=300
        )
        self.pass_input = ft.TextField(
            label="Пароль", password=True, can_reveal_password=True,
            value=self.settings.get("password"), width=300,
            on_submit=self._submit_login
        )

        # Привязываем асинхронные переходы по Enter
        async def focus_port(e):
            await self.port_input.focus()

        async def focus_user(e):
            await self.user_input.focus()

        async def focus_pass(e):
            await self.pass_input.focus()

        self.host_input.on_submit = focus_port
        self.port_input.on_submit = focus_user
        self.user_input.on_submit = focus_pass

        self.auto_login_checkbox = ft.Checkbox(label="Входить автоматически", value=self.settings.get("auto_login"))
        checkbox_row = ft.Row([self.auto_login_checkbox], width=300)
        self.status_text = ft.Text(color=ft.Colors.RED, text_align=ft.TextAlign.CENTER, width=300)

        btn_class = getattr(ft, 'Button', ft.ElevatedButton)

        self.content = ft.Column(
            controls=[
                ft.Text("Messenger", size=24, weight="bold"),
                server_row,
                self.user_input,
                self.pass_input,
                checkbox_row,
                self.status_text,
                ft.Row(
                    controls=[
                        btn_class("Вход", on_click=self._submit_login),
                        ft.TextButton("Регистрация", on_click=lambda e: self.on_show_register_callback())
                    ],
                    alignment=ft.MainAxisAlignment.CENTER
                ),
                ft.TextButton(
                    "Забыли пароль?",
                    icon=ft.Icons.LOCK_RESET,
                    icon_color=ft.Colors.GREY_500,
                    style=ft.ButtonStyle(color=ft.Colors.GREY_500),
                    on_click=lambda e: self.on_show_restore_callback()
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        )

    # --- Публичные методы для управления экраном снаружи ---
    def show_error(self, message: str):
        self.status_text.value = message
        self.status_text.color = ft.Colors.RED
        self.status_text.update()

    def show_loading(self, message: str = "Подключение..."):
        self.status_text.value = message
        self.status_text.color = ft.Colors.BLUE
        self.status_text.update()

    # --- Внутренняя логика ---
    def _submit_login(self, e):
        host = self.host_input.value.strip()
        port = self.port_input.value.strip() # <--- Читаем порт
        username = self.user_input.value.strip()
        password = self.pass_input.value.strip()
        auto_login = self.auto_login_checkbox.value

        if not host or not port or not username or not password:
            self.show_error("Заполните все поля!")
            return

        import re
        if not re.match(r"^[a-z]+\.[a-z]{2}$", username):
            self.show_error("Логин должен быть в формате фамилия.ио (в нижнем регистре), например: ivanov.dn")
            return

        self.show_loading()
        # Передаем порт наверх
        self.on_login_callback(host, port, username, password, auto_login)