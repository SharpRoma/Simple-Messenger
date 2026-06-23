import flet as ft
from datetime import datetime
from .base_dialog import BaseDialog


class ChatProfileDialog(BaseDialog):
    def __init__(self, page: ft.Page, chat_name: str, chat_type: str, members: list, files: list, on_add_click, on_download_file, on_open_media):
        super().__init__(page)

        # Разделяем файлы по категориям
        media_list = []
        audio_list = []
        doc_list = []

        for f in files:
            fname = f.get("file_name", "").lower()
            if not fname:
                continue
            
            if any(fname.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".avi", ".mkv"]):
                media_list.append(f)
            elif any(fname.endswith(ext) for ext in [".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"]):
                audio_list.append(f)
            else:
                doc_list.append(f)

        # 1. Вкладка Медиа (Фото и Видео)
        media_controls = []
        for f in media_list:
            fname = f["file_name"]
            is_video = any(fname.lower().endswith(ext) for ext in [".mp4", ".mov", ".avi", ".mkv"])
            media_controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.IMAGE if not is_video else ft.Icons.VIDEO_LIBRARY, color=ft.Colors.BLUE_400),
                    title=ft.Text(fname, size=13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    subtitle=ft.Text(f"От: {f['sender']}", size=11),
                    trailing=ft.IconButton(
                        icon=ft.Icons.OPEN_IN_NEW,
                        icon_size=16,
                        on_click=lambda e, msg_id=f["id"], is_vid=is_video, name=fname: on_open_media(msg_id, is_vid, name)
                    )
                )
            )
        media_view = ft.ListView(controls=media_controls, expand=True, spacing=5)

        # 2. Вкладка Файлы (Документы)
        doc_controls = []
        for f in doc_list:
            doc_controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.INSERT_DRIVE_FILE, color=ft.Colors.ORANGE_400),
                    title=ft.Text(f["file_name"], size=13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    subtitle=ft.Text(f"От: {f['sender']}", size=11),
                    trailing=ft.IconButton(
                        icon=ft.Icons.DOWNLOAD,
                        icon_size=16,
                        on_click=lambda e, msg_id=f["id"]: on_download_file(msg_id)
                    )
                )
            )
        doc_view = ft.ListView(controls=doc_controls, expand=True, spacing=5)

        # 3. Вкладка Аудио
        audio_controls = []
        for f in audio_list:
            audio_controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.AUDIOTRACK, color=ft.Colors.GREEN_400),
                    title=ft.Text(f["file_name"], size=13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    subtitle=ft.Text(f"От: {f['sender']}", size=11),
                    trailing=ft.IconButton(
                        icon=ft.Icons.DOWNLOAD,
                        icon_size=16,
                        on_click=lambda e, msg_id=f["id"]: on_download_file(msg_id)
                    )
                )
            )
        audio_view = ft.ListView(controls=audio_controls, expand=True, spacing=5)

        # Собираем список вкладок
        tabs_list = [
            ft.Tab(text=f"Медиа ({len(media_list)})", content=media_view),
            ft.Tab(text=f"Файлы ({len(doc_list)})", content=doc_view),
            ft.Tab(text=f"Аудио ({len(audio_list)})", content=audio_view),
        ]

        # Вкладка Участники (не показываем для "saved")
        if chat_type != "saved":
            members_list = ft.ListView(spacing=10, expand=True)
            for m in members:
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
            tabs_list.append(ft.Tab(text=f"Участники ({len(members)})", content=members_list))

        tabs = ft.Tabs(
            selected_index=0,
            tabs=tabs_list,
            expand=1
        )

        actions = []
        if chat_type == "group" and on_add_click:
            actions.append(
                ft.TextButton("Добавить участника", icon=ft.Icons.PERSON_ADD,
                              on_click=lambda e: self._handle_add(on_add_click))
            )
        actions.append(ft.TextButton("Закрыть", on_click=lambda e: self.close()))

        # Собираем окно
        self.dialog = ft.AlertDialog(
            title=ft.Text(f"Информация: {chat_name}", weight="bold"),
            content=ft.Container(content=tabs, width=380, height=350),
            actions=actions
        )

    def _handle_add(self, callback):
        self.close()
        callback()