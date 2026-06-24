import flet as ft
from datetime import datetime
from .base_dialog import BaseDialog

class SettingsDialog(BaseDialog):
    def __init__(self, page: ft.Page, current_settings: dict, on_setting_change, on_logout, on_load_sessions, on_terminate_sessions, on_get_cache_size, on_clear_cache):
        super().__init__(page)
        self.current_settings = current_settings
        self.on_setting_change = on_setting_change
        self.on_logout = on_logout
        self.on_load_sessions = on_load_sessions
        self.on_terminate_sessions = on_terminate_sessions
        self.on_get_cache_size = on_get_cache_size
        self.on_clear_cache = on_clear_cache

        # Вычисляем размеры динамически на основе размеров текущего окна страницы
        dialog_width = min(380, max(280, self.page.window.width - 40))
        dialog_height = min(380, max(280, self.page.window.height - 100))

        # Вкладка 1: Основные настройки
        self.autostart_switch = ft.Switch(
            value=self.current_settings.get("auto_start", False),
            on_change=self._handle_autostart
        )
        self.notify_switch = ft.Switch(
            value=self.current_settings.get("notify_always", False),
            on_change=self._handle_notify
        )
        autostart_row = ft.Row([
            ft.Text("Автозапуск", size=14, expand=True),
            self.autostart_switch
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        notify_row = ft.Row([
            ft.Text("Уведомлять при открытом чате", size=14, expand=True),
            self.notify_switch
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        logout_btn = ft.ElevatedButton("Выйти из аккаунта", color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_500, on_click=self._handle_logout)

        # Вкладка 2: Активные устройства
        self.sessions_list_view = ft.ListView(expand=True, spacing=5)
        self.terminate_btn = ft.ElevatedButton(
            "Завершить другие сеансы",
            icon=ft.Icons.NO_CELL,
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.RED_700,
            on_click=self._handle_terminate_others
        )

        sessions_tab_content = ft.Column([
            ft.Text("Список активных сессий вашего аккаунта:", size=14, color=ft.Colors.GREY_300),
            self.sessions_list_view,
            ft.Divider(),
            ft.Container(content=self.terminate_btn, alignment=ft.Alignment.CENTER)
        ], expand=True, spacing=10)

        # Вкладка 3: Управление кэшем
        self.cache_size_text = ft.Text(f"Размер текущего кэша: {self.on_get_cache_size()} МБ", size=14)
        self.clear_cache_btn = ft.ElevatedButton(
            "Очистить кэш",
            icon=ft.Icons.DELETE_FOREVER,
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.RED_500,
            on_click=self._handle_clear_cache
        )
        self.cleanup_switch = ft.Switch(
            value=self.current_settings.get("cache_cleanup_enabled", False),
            on_change=self._handle_cleanup_toggle
        )
        cleanup_row = ft.Row([
            ft.Text("Автоматическая очистка кэша", size=14, expand=True),
            self.cleanup_switch
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self.max_size_input = ft.TextField(
            label="Лимит размера кэша (МБ)",
            value=str(self.current_settings.get("cache_max_size_mb", 200)),
            width=150,
            input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string=""),
            on_change=self._handle_max_size_change
        )

        cache_tab_content = ft.Column([
            ft.Text("Управление локальным хранилищем:", size=14, color=ft.Colors.GREY_300),
            self.cache_size_text,
            self.clear_cache_btn,
            ft.Divider(),
            ft.Text("Автоматическая оптимизация:", size=14, color=ft.Colors.GREY_300),
            cleanup_row,
            self.max_size_input
        ], scroll=ft.ScrollMode.AUTO, spacing=15)

        # Компоновка вкладками
        tabs = ft.Tabs(
            selected_index=0,
            length=3,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Основные"),
                            ft.Tab(label="Устройства"),
                            ft.Tab(label="Кэш")
                        ]
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            ft.Container(
                                content=ft.Column([
                                    autostart_row,
                                    notify_row,
                                    ft.Divider(),
                                    logout_btn
                                ], scroll=ft.ScrollMode.AUTO, spacing=15),
                                padding=ft.Padding.symmetric(vertical=10),
                                width=dialog_width - 40
                            ),
                            ft.Container(
                                content=sessions_tab_content,
                                padding=ft.Padding.symmetric(vertical=10),
                                expand=True,
                                width=dialog_width - 40
                            ),
                            ft.Container(
                                content=cache_tab_content,
                                padding=ft.Padding.symmetric(vertical=10),
                                width=dialog_width - 40
                            )
                        ]
                    )
                ]
            ),
            expand=1
        )

        self.dialog = ft.AlertDialog(
            title=ft.Text("Настройки", weight="bold"),
            content=ft.Container(content=tabs, width=dialog_width, height=dialog_height),
            actions=[ft.TextButton("Закрыть", on_click=lambda e: self.close())]
        )

    def show(self):
        super().show()
        # Загружаем сессии при открытии настроек
        self.page.run_task(self.fetch_sessions)

    async def fetch_sessions(self):
        self.sessions_list_view.controls = [
            ft.Row([
                ft.ProgressRing(width=20, height=20),
                ft.Text("Загрузка активных сеансов...", size=14)
            ], alignment=ft.MainAxisAlignment.CENTER)
        ]
        self.sessions_list_view.update()

        try:
            sessions = await self.on_load_sessions()
            controls = []
            for s in sessions:
                created_dt = datetime.fromtimestamp(s["created_at"]).strftime("%d.%m.%Y %H:%M")
                title = f"{s['ip_address']}"
                if s["is_current"]:
                    title += " (Этот сеанс)"
                controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.DEVICES, color=ft.Colors.BLUE_400 if s["is_current"] else ft.Colors.GREY_400),
                        title=ft.Text(title, weight="bold" if s["is_current"] else "normal", size=14),
                        subtitle=ft.Text(f"Вход: {created_dt}", size=12),
                    )
                )
            if not controls:
                controls.append(ft.Text("Нет активных устройств", color=ft.Colors.GREY_500))
            self.sessions_list_view.controls = controls
        except Exception as e:
            self.sessions_list_view.controls = [ft.Text(f"Ошибка загрузки: {e}", color=ft.Colors.RED)]

        self.sessions_list_view.update()

    async def _handle_terminate_others(self, e):
        self.terminate_btn.disabled = True
        self.terminate_btn.update()
        try:
            success, msg = await self.on_terminate_sessions()
            if success:
                await self.fetch_sessions()
        except Exception:
            pass
        self.terminate_btn.disabled = False
        self.terminate_btn.update()

    def _handle_autostart(self, e):
        self.current_settings["auto_start"] = self.autostart_switch.value
        self.on_setting_change(self.current_settings)

    def _handle_notify(self, e):
        self.current_settings["notify_always"] = self.notify_switch.value
        self.on_setting_change(self.current_settings)

    def _handle_logout(self, e):
        self.close()
        self.on_logout()

    def _handle_cleanup_toggle(self, e):
        self.current_settings["cache_cleanup_enabled"] = self.cleanup_switch.value
        self.on_setting_change(self.current_settings)

    def _handle_max_size_change(self, e):
        val = self.max_size_input.value.strip()
        if val.isdigit():
            self.current_settings["cache_max_size_mb"] = int(val)
        else:
            self.current_settings["cache_max_size_mb"] = 200
        self.on_setting_change(self.current_settings)

    async def _handle_clear_cache(self, e):
        self.clear_cache_btn.disabled = True
        self.clear_cache_btn.update()
        try:
            self.on_clear_cache()
            self.cache_size_text.value = f"Размер текущего кэша: {self.on_get_cache_size()} МБ"
            self.cache_size_text.update()
        except Exception:
            pass
        self.clear_cache_btn.disabled = False
        self.clear_cache_btn.update()