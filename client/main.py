import flet as ft
import os
import platform
import subprocess
import threading
from PIL import Image, ImageDraw
from plyer import notification
import config
from gui import MessengerGUI


# --- АВТОГЕНЕРАЦИЯ ИКОНОК ---
def create_icons_if_needed():
    if not config.ASSETS_DIR.exists():
        config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    if not config.ICON_PATH.exists():
        img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(43, 43, 43))
        d.text((16, 24), "MSG", fill=(255, 255, 255))
        img.save(config.ICON_PATH)

    if not config.UNREAD_ICON_PATH.exists():
        img = Image.open(config.ICON_PATH).copy()
        ImageDraw.Draw(img).ellipse((44, 4, 64, 24), fill=(255, 0, 0))
        img.save(config.UNREAD_ICON_PATH)

    # СПЕЦИАЛЬНО ДЛЯ WINDOWS: Делаем формат .ico для уведомлений Центра Windows
    icon_ico_path = config.ASSETS_DIR / "icon.ico"
    if not icon_ico_path.exists():
        img = Image.open(config.ICON_PATH)
        img.save(icon_ico_path, format="ICO", sizes=[(64, 64)])


create_icons_if_needed()

tray_icon = None
flet_page = None


def notify_os(title, text):
    try:
        if platform.system() == "Darwin":
            subprocess.run(["osascript", "-e",
                            f'display notification "{text.replace("\"", "\\\"")}" with title "Simple Messenger" subtitle "{title.replace("\"", "\\\"")}"'])
        else:
            # На Windows передаем абсолютный путь к сгенерированному .ico
            icon_ico = str(config.ASSETS_DIR / "icon.ico")
            notification.notify(title=title, message=text, app_name="Simple Messenger", app_icon=icon_ico, timeout=5)
    except Exception as e:
        print(f"Ошибка уведомления: {e}")


def set_tray_badge(has_unread: bool):
    global tray_icon
    if tray_icon and platform.system() != "Darwin":
        try:
            tray_icon.icon = Image.open(str(config.UNREAD_ICON_PATH if has_unread else config.ICON_PATH))
        except:
            pass


def window_event_handler(e):
    global flet_page
    if e.data == "close":
        if platform.system() == "Darwin":
            flet_page.window.minimized = True
        else:
            flet_page.window.visible = False
        flet_page.update()
    elif e.data in ["focus", "restore"]:
        set_tray_badge(False)


def main_flet(page: ft.Page):
    global flet_page
    flet_page = page

    # ЖЕСТКО ЗАДАЕМ ИКОНКУ ОКНУ (Для панели задач Windows)
    page.title = "Simple Messenger"
    page.window.icon = "icon.ico" if platform.system() == "Windows" else "icon.png"

    page.window.prevent_close = True
    page.window.on_event = window_event_handler
    MessengerGUI(page, notify_os, set_tray_badge)


# --- ИНТЕГРАЦИЯ PYSTRAY (ДЛЯ WINDOWS) ---
def restore_window(icon, item_):
    global flet_page
    set_tray_badge(False)
    if flet_page:
        flet_page.window.visible = True
        flet_page.window.minimized = False
        flet_page.update()
        try:
            flet_page.window.focus()
        except:
            pass


def quit_app(icon, item_):
    icon.stop()
    os._exit(0)


def start_tray():
    import pystray
    from pystray import MenuItem as item
    global tray_icon
    tray_icon = pystray.Icon("SimpleMessenger", Image.open(str(config.ICON_PATH)), "Simple Messenger",
                             pystray.Menu(item('Развернуть', restore_window, default=True), item('Выход', quit_app)))
    tray_icon.run()


if __name__ == "__main__":
    if platform.system() != "Darwin":
        threading.Thread(target=start_tray, daemon=True).start()
    if hasattr(ft, 'run'):
        ft.run(main_flet, assets_dir=str(config.ASSETS_DIR))
    else:
        ft.app(main_flet, assets_dir=str(config.ASSETS_DIR))