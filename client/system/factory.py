import platform
import flet as ft


def get_system_adapter(page: ft.Page, config):
    system_name = platform.system()

    if system_name == "Darwin":
        from .macos import MacOSAdapter
        return MacOSAdapter(page)
    else:
        from .windows import WindowsAdapter
        return WindowsAdapter(
            page,
            icon_path=str(config.ICON_PATH),
            unread_icon_path=str(config.UNREAD_ICON_PATH),
            ico_path=str(config.ASSETS_DIR / "icon.ico")
        )