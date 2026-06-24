import flet as ft
from datetime import datetime
from .base_dialog import BaseDialog
import re
from system.utils import open_file_in_default_app, open_url_in_browser, open_folder_and_select_file

class ChatProfileDialog(BaseDialog):
    def __init__(self, page: ft.Page, chat_name: str, chat_type: str, members: list, files: list, links: list, on_add_click, on_download_file, on_open_media):
        super().__init__(page)

        self.chat_name = chat_name
        self.chat_type = chat_type
        self.members = members
        self.files = files
        self.links = links
        self.on_add_click = on_add_click
        self.on_download_file = on_download_file
        self.on_open_media = on_open_media

        self.tabs_container = ft.Container()
        self.rebuild_tabs()

        actions = []
        if self.chat_type == "group" and self.on_add_click:
            actions.append(
                ft.TextButton("Добавить участника", icon=ft.Icons.PERSON_ADD,
                              on_click=lambda e: self._handle_add(self.on_add_click))
            )
        actions.append(ft.TextButton("Закрыть", on_click=lambda e: self.close()))

        # Собираем окно
        # Вычисляем размеры динамически на основе размеров текущего окна страницы
        dialog_width = min(380, max(280, self.page.window.width - 40))
        dialog_height = min(380, max(280, self.page.window.height - 100))

        self.dialog = ft.AlertDialog(
            title=ft.Text(f"Информация: {self.chat_name}", weight="bold"),
            content=ft.Container(content=self.tabs_container, width=dialog_width, height=dialog_height),
            actions=actions
        )

    def rebuild_tabs(self):
        def open_folder_action(path):
            open_folder_and_select_file(path)

        # Разделяем файлы по категориям
        media_list = []
        doc_list = []

        for f in self.files:
            fname = f.get("file_name", "").lower()
            if not fname:
                continue
            
            if any(fname.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".avi", ".mkv"]):
                media_list.append(f)
            else:
                doc_list.append(f)

        # 1. Вкладка Медиа (Фото и Видео)
        media_controls = []
        for f in media_list:
            fname = f["file_name"]
            is_video = any(fname.lower().endswith(ext) for ext in [".mp4", ".mov", ".avi", ".mkv"])
            
            import os
            local_path = f.get("local_path")
            is_downloaded = False
            if local_path:
                try:
                    if os.path.exists(local_path):
                        is_downloaded = True
                except Exception:
                    pass

            if is_downloaded:
                def make_open_folder(path):
                    return lambda e: open_folder_action(path)
                trailing_btn = ft.IconButton(
                    icon=ft.Icons.FOLDER_OPEN,
                    icon_color=ft.Colors.GREEN_400,
                    icon_size=16,
                    on_click=make_open_folder(local_path),
                    tooltip="Показать в Finder/проводнике"
                )
            else:
                def make_download(mid, name):
                    return lambda e: self.on_download_file(mid, name)
                trailing_btn = ft.IconButton(
                    icon=ft.Icons.DOWNLOAD,
                    icon_size=16,
                    on_click=make_download(f["id"], fname),
                    tooltip="Скачать"
                )

            def make_preview(mid, is_v, name):
                return lambda e: self.on_open_media(mid, is_v, name)

            media_controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.IMAGE if not is_video else ft.Icons.VIDEO_LIBRARY, color=ft.Colors.BLUE_400),
                    title=ft.Text(fname, size=13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    subtitle=ft.Text(f"От: {f['sender']}", size=11),
                    trailing=trailing_btn,
                    on_click=make_preview(f["id"], is_video, fname)
                )
            )
        media_view = ft.ListView(controls=media_controls, expand=True, spacing=5)

        # 2. Вкладка Файлы (Документы + Аудио)
        doc_controls = []
        for f in doc_list:
            import os
            local_path = f.get("local_path")
            is_downloaded = False
            if local_path:
                try:
                    if os.path.exists(local_path):
                        is_downloaded = True
                except Exception:
                    pass

            if is_downloaded:
                def make_open_folder(path):
                    return lambda e: open_folder_action(path)
                trailing_btn = ft.IconButton(
                    icon=ft.Icons.FOLDER_OPEN,
                    icon_color=ft.Colors.GREEN_400,
                    icon_size=16,
                    on_click=make_open_folder(local_path),
                    tooltip="Показать в Finder/проводнике"
                )
            else:
                def make_download(mid, fname):
                    return lambda e: self.on_download_file(mid, fname)
                trailing_btn = ft.IconButton(
                    icon=ft.Icons.DOWNLOAD,
                    icon_size=16,
                    on_click=make_download(f["id"], f["file_name"]),
                    tooltip="Скачать"
                )

            def make_row_click(is_dl, path, mid, fname):
                if is_dl and path:
                    return lambda e: open_file_in_default_app(path)
                else:
                    return lambda e: self.on_download_file(mid, fname)

            fname_lower = f["file_name"].lower()
            is_audio = any(fname_lower.endswith(ext) for ext in [".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"])
            icon_type = ft.Icons.AUDIOTRACK if is_audio else ft.Icons.INSERT_DRIVE_FILE
            icon_color = ft.Colors.GREEN_400 if is_audio else ft.Colors.ORANGE_400

            doc_controls.append(
                ft.ListTile(
                    leading=ft.Icon(icon_type, color=icon_color),
                    title=ft.Text(f["file_name"], size=13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    subtitle=ft.Text(f"От: {f['sender']}", size=11),
                    trailing=trailing_btn,
                    on_click=make_row_click(is_downloaded, local_path, f["id"], f["file_name"])
                )
            )
        doc_view = ft.ListView(controls=doc_controls, expand=True, spacing=5)

        # 3. Вкладка Ссылки (Links)
        URL_PATTERN = re.compile(r'(https?://[^\s]+)')
        link_controls = []
        for l in self.links:
            text = l.get("text", "")
            found_urls = URL_PATTERN.findall(text)
            for url in found_urls:
                def make_url_click(target_url):
                    return lambda e: open_url_in_browser(target_url)

                link_controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.LINK, color=ft.Colors.BLUE_400),
                        title=ft.Text(url, size=13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.BLUE_200),
                        subtitle=ft.Text(f"От: {l['sender']}", size=11),
                        on_click=make_url_click(url),
                        tooltip="Кликните, чтобы открыть в браузере"
                    )
                )
        link_view = ft.ListView(controls=link_controls, expand=True, spacing=5)

        # Собираем список заголовков и содержимого вкладок
        tab_headers = [
            ft.Tab(label=f"Медиа ({len(media_list)})"),
            ft.Tab(label=f"Файлы ({len(doc_list)})"),
            ft.Tab(label=f"Ссылки ({len(link_controls)})"),
        ]
        tab_views = [
            media_view,
            doc_view,
            link_view,
        ]

        # Вкладка Участники (не показываем для "saved")
        if self.chat_type != "saved":
            members_list = ft.ListView(spacing=10, expand=True)
            for m in self.members:
                if m.get('is_online'):
                    status_text = "в сети"
                    status_color = ft.Colors.GREEN
                elif m.get('last_seen'):
                    ts = datetime.fromtimestamp(m['last_seen']).strftime('%d.%m %H:%M')
                    status_text = f"был(а) {ts}"
                    status_color = ft.Colors.GREY_500
                else:
                    status_text = "оффлайн"
                    status_color = ft.Colors.GREY_500

                members_list.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.PERSON),
                        title=ft.Text(m['username']),
                        subtitle=ft.Text(status_text, color=status_color)
                    )
                )
            tab_headers.append(ft.Tab(label=f"Участники ({len(self.members)})"))
            tab_views.append(members_list)

        # Сохраняем выбранный индекс таба
        selected_index = 0
        if self.tabs_container.content and isinstance(self.tabs_container.content, ft.Tabs):
            selected_index = self.tabs_container.content.selected_index

        tabs = ft.Tabs(
            selected_index=selected_index,
            length=len(tab_headers),
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(tabs=tab_headers),
                    ft.TabBarView(expand=True, controls=tab_views)
                ]
            ),
            expand=1
        )
        self.tabs_container.content = tabs

    def update_file_local_path(self, msg_id: int, filepath: str):
        for f in self.files:
            if f.get("id") == msg_id:
                f["local_path"] = filepath
                break
        self.rebuild_tabs()
        self.dialog.update()

    def _handle_add(self, callback):
        self.close()
        callback()