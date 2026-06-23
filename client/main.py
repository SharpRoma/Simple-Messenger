import flet as ft
import config
import platform
import logging
from system.logger import setup_logger
from system.factory import get_system_adapter
from ui.main_window import MainWindow

# Инициализируем логирование на клиенте
setup_logger(config.APP_DIR)
logger = logging.getLogger("messenger.main")


def main(page: ft.Page):
    logger.info("Запуск приложения клиента...")
    # 1. Автогенерация иконок (вызывается из config перед стартом GUI)
    config.create_icons_if_needed()

    # 2. Инициализация системного адаптера (Mac или Win)
    os_adapter = get_system_adapter(page, config)
    os_adapter.setup_tray()

    # 3. Настройка окна Flet
    # 3. Настройка окна Flet
    page.title = "Simple Messenger"

    page.window.icon = "icon.ico" if platform.system() == "Windows" else "icon.png"

    # ПЕРЕХВАТЫВАЕМ КРЕСТИК ТОЛЬКО НА WINDOWS (ради системного трея)
    if platform.system() == "Windows":
        page.window.prevent_close = True

        def window_event_handler(e):
            # Flet 0.85+ передает тип события в e.type, старые версии в e.data
            event_str = ""
            if hasattr(e, "type") and hasattr(e.type, "name"):
                event_str = e.type.name.lower()  # Вернет "close", "focus" и т.д.
            elif isinstance(e.data, str):
                event_str = e.data.lower()

            os_adapter.handle_window_event(event_str)

        page.window.on_event = window_event_handler
        page.update()

    # 4. Запуск главного контроллера интерфейса
    # В качестве settings_manager мы пока передадим сам модуль config
    MainWindow(page, system_adapter=os_adapter, settings_manager=config)


if __name__ == "__main__":
    ft.run(main, assets_dir=str(config.ASSETS_DIR))