import sys
import flet as ft
import config
import platform
import logging

if sys.platform == "win32":
    import ctypes
    try:
        # Устанавливаем уникальный AppUserModelID, чтобы Windows корректно группировала
        # окна приложения и не сбрасывала иконку на логотип Flet при закреплении на панели задач
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SharpRoma.SimpleMessenger.Client")
    except Exception:
        pass
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

    # Проверка на запуск единственной копии (Single Instance Lock)
    import socket
    import sys
    import threading

    multi_instance = "--multi" in sys.argv or "--test" in sys.argv
    port = 48951

    if not multi_instance:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('127.0.0.1', port))
            s.sendall(b"restore")
            s.close()
            logger.info("Другая копия приложения уже запущена. Отправлен сигнал развернуть окно. Завершение работы.")
            try:
                page.window.destroy()
            except Exception:
                pass
            return
        except socket.error:
            pass

    def listen_restore_signals():
        if multi_instance:
            return  # Не слушаем порт в режиме мульти-запуска, чтобы не мешать другим копиям
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(('127.0.0.1', port))
            server.listen(1)
            while True:
                conn, addr = server.accept()
                data = conn.recv(1024)
                if data == b"restore":
                    os_adapter.restore_window()
                conn.close()
        except Exception as ex:
            logger.error(f"Ошибка прослушивания сигналов восстановления: {ex}")

    threading.Thread(target=listen_restore_signals, daemon=True).start()

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