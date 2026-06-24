import flet as ft
from datetime import datetime
from .base_dialog import BaseDialog

class SettingsDialog(BaseDialog):
    def __init__(self, page: ft.Page, current_settings: dict, on_setting_change, on_logout, on_load_sessions, on_terminate_sessions):
        super().__init__(page)
        self.current_settings = current_settings
        self.on_setting_change = on_setting_change
        self.on_logout = on_logout
        self.on_load_sessions = on_load_sessions
        self.on_terminate_sessions = on_terminate_sessions

        # Вкладка 1: Основные настройки
        self.autostart_switch = ft.Switch(
            label="Автозапуск",
            value=self.current_settings.get("auto_start", False),
            on_change=self._handle_autostart
        )
        self.notify_switch = ft.Switch(
            label="Уведомлять при открытом чате",
            value=self.current_settings.get("notify_always", False),
            on_change=self._handle_notify
        )
        logout_btn = ft.ElevatedButton("Выйти из аккаунта", color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_500, on_click=self._handle_logout)

        # Вкладка 2: Активные устройства
        self.sessions_list_view = ft.ListView(expand=True, spacing=5, height=200)
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
        ], tight=True, spacing=10)

        # Компоновка вкладками
        tabs = ft.Tabs(
            selected_index=0,
            length=2,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Основные"),
                            ft.Tab(label="Устройства")
                        ]
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            ft.Container(
                                content=ft.Column([
                                    self.autostart_switch,
                                    self.notify_switch,
                                    ft.Divider(),
                                    logout_btn
                                ], tight=True, spacing=15),
                                padding=ft.Padding.symmetric(vertical=10)
                            ),
                            ft.Container(
                                content=sessions_tab_content,
                                padding=ft.Padding.symmetric(vertical=10)
                            )
                        ]
                    )
                ]
            ),
            expand=1
        )

        self.dialog = ft.AlertDialog(
            title=ft.Text("Настройки", weight="bold"),
            content=ft.Container(content=tabs, width=380, height=350),
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