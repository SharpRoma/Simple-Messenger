import flet as ft
import os
import platform
import subprocess
import threading
from PIL import Image, ImageDraw
from plyer import notification

from gui import MessengerGUI


# --- АВТОГЕНЕРАЦИЯ ИКОНОК ---
def create_icons_if_needed():
    if not os.path.exists("assets"): os.makedirs("assets")
    icon_path, unread_path = "assets/icon.png", "assets/icon_unread.png"
    if not os.path.exists(icon_path):
        img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(43, 43, 43))
        d.text((16, 24), "MSG", fill=(255, 255, 255))
        img.save(icon_path)
    if not os.path.exists(unread_path):
        img = Image.open(icon_path).copy()
        ImageDraw.Draw(img).ellipse((44, 4, 64, 24), fill=(255, 0, 0))
        img.save(unread_path)


create_icons_if_needed()

# --- ГЛОБАЛЬНЫЕ ССЫЛКИ ДЛЯ ОС ---
tray_icon = None
flet_page = None


def notify_os(title, text):
    """Надежные уведомления ОС"""
    try:
        if platform.system() == "Darwin":
            safe_text = text.replace('"', '\\"')
            safe_title = title.replace('"', '\\"')
            subprocess.run(["osascript", "-e",
                            f'display notification "{safe_text}" with title "Simple Messenger" subtitle "{safe_title}"'])
        else:
            notification.notify(title=title, message=text, app_name="Simple Messenger",
                                app_icon=os.path.abspath("assets/icon.png") if os.name == 'nt' else None, timeout=5)
    except Exception as e:
        print(f"Ошибка уведомления: {e}")


def set_tray_badge(has_unread: bool):
    """Смена иконки в трее (только для Windows/Linux)"""
    global tray_icon
    if tray_icon and platform.system() != "Darwin":
        try:
            tray_icon.icon = Image.open("assets/icon_unread.png" if has_unread else "assets/icon.png")
        except:
            pass


def window_event_handler(e):
    """Обработка крестика и фокуса"""
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
    page.window.prevent_close = True
    page.window.on_event = window_event_handler
    # Инициализируем графику и передаем ей коллбэки для ОС
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
    tray_icon = pystray.Icon("SimpleMessenger", Image.open("assets/icon.png"), "Simple Messenger",
                             pystray.Menu(item('Развернуть', restore_window, default=True), item('Выход', quit_app)))
    tray_icon.run()


if __name__ == "__main__":
    if platform.system() != "Darwin":
        threading.Thread(target=start_tray, daemon=True).start()

    # Запускаем Flet в главном потоке (сохраняем Ctrl+C и Dock)
    if hasattr(ft, 'run'):
        ft.run(main_flet, assets_dir="assets")
    else:
        ft.app(main_flet, assets_dir="assets")