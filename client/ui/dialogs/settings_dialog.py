import flet as ft
from .base_dialog import BaseDialog

class SettingsDialog(BaseDialog):
    def __init__(self, page: ft.Page, current_settings: dict, on_setting_change, on_logout):
        super().__init__(page)
        self.current_settings = current_settings
        self.on_setting_change = on_setting_change
        self.on_logout = on_logout

        # Элементы интерфейса
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
        logout_btn = ft.ElevatedButton("Выйти", color=ft.Colors.RED, on_click=self._handle_logout)

        self.dialog = ft.AlertDialog(
            title=ft.Text("Настройки", weight="bold"),
            content=ft.Column([self.autostart_switch, self.notify_switch, ft.Divider(), logout_btn], tight=True),
            actions=[ft.TextButton("Закрыть", on_click=lambda e: self.close())]
        )

    def _handle_autostart(self, e):
        self.current_settings["auto_start"] = self.autostart_switch.value
        self.on_setting_change(self.current_settings)

    def _handle_notify(self, e):
        self.current_settings["notify_always"] = self.notify_switch.value
        self.on_setting_change(self.current_settings)

    def _handle_logout(self, e):
        self.close()
        self.on_logout()