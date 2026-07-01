import os
import sys
if sys.platform == "win32":
    os.environ["FLET_HIDE_WINDOW_ON_START"] = "true"

# Ранний перехватчик ошибок импорта
try:
    import flet as ft
    import config
    import platform
    import logging
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SharpRoma.SimpleMessenger.Client")
        except Exception:
            pass
    from system.logger import setup_logger
    from system.factory import get_system_adapter
    from ui.main_window import MainWindow
except Exception as early_err:
    import traceback
    try:
        if sys.platform == "win32":
            app_data_path = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'SimpleMessenger')
        elif sys.platform == "darwin":
            app_data_path = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'SimpleMessenger')
        else:
            app_data_path = os.path.join(os.path.expanduser('~'), '.config', 'SimpleMessenger')
        os.makedirs(app_data_path, exist_ok=True)
        with open(os.path.join(app_data_path, 'early_crash.log'), 'w', encoding='utf-8') as f:
            f.write("Early import crash:\n")
            traceback.print_exc(file=f)
    except Exception:
        pass
    sys.exit(1)

# Инициализируем логирование на клиенте
setup_logger(config.APP_DIR)
logger = logging.getLogger("messenger.main")


def main(page: ft.Page):
    logger.info("Запуск приложения клиента (main)...")
    
    def on_disconnect(e):
        logger.info("Сессия Flet закрыта. Завершение процесса Python.")
        import os
        os._exit(0)
    page.on_disconnect = on_disconnect

    try:
        logger.info("Шаг 1: Автогенерация иконок...")
        config.create_icons_if_needed()

        logger.info("Шаг 2: Инициализация системного адаптера...")
        os_adapter = get_system_adapter(page, config)
        
        logger.info("Шаг 3: Настройка трея...")
        os_adapter.setup_tray()

        logger.info("Шаг 4: Проверка на запуск единственной копии...")
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
                print("ОШИБКА: Другая копия приложения уже запущена на порту 48951! Отправлен сигнал восстановления. Завершение работы.")
                try:
                    page.window.destroy()
                except Exception:
                    pass
                return
            except socket.error:
                logger.info("Других копий не найдено, продолжаем запуск.")

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

        logger.info("Шаг 5: Настройка размеров окна...")
        # 3. Настройка окна Flet
        page.title = "Simple Messenger"
        page.window.width = 400
        page.window.height = 550
        page.window.min_width = 350
        page.window.min_height = 400
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

        logger.info("Шаг 6: Делаем окно видимым...")
        page.window.visible = True
        page.window.minimized = False
        page.window.focused = True
        
        # Трюк для вывода окна на передний план при старте
        page.window.always_on_top = True
        page.update()
        page.window.always_on_top = False
        page.update()

        logger.info("Шаг 7: Запуск главного контроллера MainWindow...")
        MainWindow(page, system_adapter=os_adapter, settings_manager=config)
        logger.info("Шаг 8: Метод main завершил выполнение успешно.")
    except Exception as ex:
        logger.exception("КРИТИЧЕСКАЯ ОШИБКА в main():")


if __name__ == "__main__":
    ft.app(target=main, assets_dir=str(config.ASSETS_DIR))