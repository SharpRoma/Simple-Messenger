import flet as ft
import config
from system.factory import get_system_adapter
from ui.main_window import MainWindow


def main(page: ft.Page):
    # 1. Автогенерация иконок (вызывается из config перед стартом GUI)
    config.create_icons_if_needed()

    # 2. Инициализация системного адаптера (Mac или Win)
    os_adapter = get_system_adapter(page, config)
    os_adapter.setup_tray()

    # 3. Настройка окна Flet
    page.title = "Simple Messenger"
    page.window.prevent_close = True

    # Жестко прописываем иконку для панели задач Windows
    import platform
    page.window.icon = "icon.ico" if platform.system() == "Windows" else "icon.png"

    # Подключаем системные события окна (крестик, сворачивание)
    def window_event_handler(e):
        os_adapter.handle_window_event(e.data)

    page.window.on_event = window_event_handler

    # 4. Запуск главного контроллера интерфейса
    # В качестве settings_manager мы пока передадим сам модуль config
    MainWindow(page, system_adapter=os_adapter, settings_manager=config)


if __name__ == "__main__":
    ft.run(main, assets_dir=str(config.ASSETS_DIR))