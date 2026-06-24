import flet as ft
from datetime import datetime
import os
import platform
import subprocess
import logging

logger = logging.getLogger("messenger.chat_screen")

def open_file_in_default_app(filepath: str):
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", filepath])
        elif system == "Windows":
            os.startfile(filepath)
        else:
            subprocess.run(["xdg-open", filepath])
    except Exception as err:
        logger.error(f"Failed to open file: {err}")


class ChatScreen(ft.Container):
    def __init__(
            self,
            current_username: str,
            on_send_message,
            on_typing,
            on_attach_file,
            on_open_drawer,
            on_toggle_pin,
            on_copy_message,
            on_delete_message,
            on_download_file,
            on_input_focus,
            on_open_profile,
            on_load_more_history,
            on_get_media_url,
            on_open_media,
            on_edit_message,
            on_cancel_edit,
            on_delete_attached_file,
            on_search_messages,
            on_clear_search
    ):
        super().__init__()
        self.expand = True
        self.current_username = current_username

        self.on_send_message = on_send_message
        self.on_typing = on_typing
        self.on_attach_file = on_attach_file
        self.on_open_drawer = on_open_drawer
        self.on_toggle_pin = on_toggle_pin
        self.on_copy_message = on_copy_message
        self.on_delete_message = on_delete_message
        self.on_download_file = on_download_file
        self.on_input_focus = on_input_focus

        self.on_open_profile = on_open_profile
        self.on_load_more_history = on_load_more_history
        self.on_get_media_url = on_get_media_url
        self.on_open_media = on_open_media
        self.on_edit_message = on_edit_message
        self.on_cancel_edit = on_cancel_edit
        self.on_delete_attached_file = on_delete_attached_file
        self.on_search_messages = on_search_messages
        self.on_clear_search = on_clear_search

        self.is_pinned = False
        self._build_ui()

    def _build_ui(self):
        self.chat_history = ft.ListView(expand=True, spacing=5, auto_scroll=True, on_scroll=self._handle_scroll)
        self.msg_input = ft.TextField(
            hint_text="Написать сообщение...", expand=True,
            on_submit=self._submit_message,
            on_focus=lambda e: self.on_input_focus(),
            on_change=lambda e: self.on_typing()
        )

        self.chat_title = ft.Text("Simple Messenger", size=16, weight="bold")
        self.chat_subtitle = ft.Text(" ", size=8, color=ft.Colors.GREY_400)  # Подзаголовок со статусом! (по умолчанию пробел для фиксации высоты)

        title_col = ft.Column(
            [self.chat_title, self.chat_subtitle],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0
        )
        title_container = ft.Container(
            content=title_col,
            expand=True,
            margin=ft.Margin(left=0, top=4, right=0, bottom=0)
        )

        self.pin_btn = ft.IconButton(icon=ft.Icons.PUSH_PIN, icon_color=ft.Colors.WHITE54, tooltip="Поверх всех",
                                     on_click=self._toggle_pin)

        # Кнопка Поиска
        self.search_btn = ft.IconButton(
            icon=ft.Icons.SEARCH,
            icon_color=ft.Colors.WHITE54,
            tooltip="Поиск сообщений",
            on_click=self._toggle_search_panel
        )

        # Кнопка Инфо (Профиль)
        self.info_btn = ft.IconButton(
            icon=ft.Icons.INFO_OUTLINE,
            tooltip="Профиль чата",
            on_click=lambda e: self.on_open_profile(),
            visible=False
        )

        header_row = ft.Row([
            ft.IconButton(
                icon=ft.Icons.MENU,
                on_click=lambda e: self.on_open_drawer()
            ),
            title_container,
            ft.Row(
                [self.info_btn, self.search_btn, self.pin_btn],
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER)

        input_row = ft.Row([
            ft.IconButton(
                icon=ft.Icons.ATTACH_FILE,
                icon_color=ft.Colors.GREY_400,
                on_click=lambda e: self.on_attach_file()
            ),
            self.msg_input,
            ft.IconButton(icon=ft.Icons.SEND, icon_color=ft.Colors.BLUE, on_click=self._submit_message)
        ])

        # Панель редактирования сообщения (Telegram-style)
        self.edit_label = ft.Text("Редактирование...", size=12, color=ft.Colors.BLUE)
        self.delete_attached_file_btn = ft.IconButton(
            icon=ft.Icons.DELETE_SWEEP_OUTLINED,
            icon_size=16,
            icon_color=ft.Colors.RED_400,
            tooltip="Удалить файл из сообщения",
            on_click=self._handle_delete_attached_file_click,
            visible=False
        )
        self.cancel_edit_btn = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_size=16,
            icon_color=ft.Colors.GREY_400,
            tooltip="Отменить редактирование",
            on_click=self._handle_cancel_edit_click
        )

        self.edit_panel = ft.Row([
            ft.Icon(ft.Icons.EDIT, size=16, color=ft.Colors.BLUE),
            self.edit_label,
            self.delete_attached_file_btn,
            self.cancel_edit_btn
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, visible=False)

        # Панель поиска сообщений
        self.search_input = ft.TextField(
            hint_text="Поиск в этом чате...",
            expand=True,
            on_submit=self._submit_search,
            text_size=13,
            content_padding=5,
            height=30
        )
        self.close_search_btn = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_size=16,
            icon_color=ft.Colors.GREY_400,
            tooltip="Закрыть поиск",
            on_click=self._handle_close_search_click
        )
        self.search_panel = ft.Row([
            ft.Icon(ft.Icons.SEARCH, size=16, color=ft.Colors.GREY_400),
            self.search_input,
            self.close_search_btn
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, visible=False)

        self.content = ft.Column([
            header_row, ft.Divider(height=1),
            self.search_panel,
            ft.Container(
                content=self.chat_history,
                expand=True,
                border_radius=5,
                padding=10,
                bgcolor="#1e1e1e"
            ),
            self.edit_panel,
            input_row
        ],
        expand=True
        )

    def set_chat_title(self, title: str, subtitle: str = "", show_info: bool = False, is_online: bool = False):
        self.chat_title.value = title
        self.chat_subtitle.value = subtitle if subtitle else " "
        self.chat_subtitle.color = ft.Colors.GREEN if is_online else ft.Colors.GREY_400

        self.info_btn.visible = show_info

        try:
            self.chat_title.update()
            self.chat_subtitle.update()
            self.info_btn.update()
        except Exception:
            pass

    # --- Внутренняя логика UI ---
    def _submit_message(self, e):
        text = self.msg_input.value.strip()
        if text or self.edit_panel.visible:  # Разрешаем отправку в режиме редактирования даже пустого текста (если останется файл)
            self.msg_input.value = ""
            try:
                self.msg_input.update()
            except Exception:
                pass
            self.on_send_message(text)

    def _toggle_pin(self, e):
        self.is_pinned = not self.is_pinned
        self.pin_btn.icon_color = ft.Colors.RED if self.is_pinned else ft.Colors.WHITE54
        self.pin_btn.update()
        self.on_toggle_pin(self.is_pinned)

    def _handle_cancel_edit_click(self, e):
        self.on_cancel_edit()

    def _handle_delete_attached_file_click(self, e):
        self.on_delete_attached_file()

    def _toggle_search_panel(self, e):
        self.search_panel.visible = not self.search_panel.visible
        if self.search_panel.visible:
            self.search_input.focus()
        else:
            self.search_input.value = ""
            self.on_clear_search()
        try:
            self.search_panel.update()
        except Exception:
            pass

    def _submit_search(self, e):
        query = self.search_input.value.strip()
        if query:
            self.on_search_messages(query)

    def _handle_close_search_click(self, e):
        self.search_input.value = ""
        self.search_panel.visible = False
        self.on_clear_search()
        try:
            self.search_panel.update()
        except Exception:
            pass

    # --- Публичные методы управления режимом редактирования ---
    def start_edit_mode(self, text: str, file_name: str = None):
        self.edit_label.value = f"Редактирование: {text[:20]}..." if len(text) > 20 else f"Редактирование: {text}"
        if file_name:
            self.edit_label.value += f" | 📎 {file_name}"
            self.delete_attached_file_btn.visible = True
        else:
            self.delete_attached_file_btn.visible = False

        self.edit_panel.visible = True
        self.msg_input.value = text
        self.msg_input.focus()

        try:
            self.edit_panel.update()
            self.msg_input.update()
        except Exception:
            pass

    def stop_edit_mode(self):
        self.edit_panel.visible = False
        self.delete_attached_file_btn.visible = False
        self.msg_input.value = ""

        try:
            self.edit_panel.update()
            self.msg_input.update()
        except Exception:
            pass

    # --- Публичные методы для истории ---
    def clear_messages(self):
        self.chat_history.controls.clear()
        try: self.chat_history.update()
        except Exception: pass

    def add_system_message(self, text: str, color=ft.Colors.WHITE):
        row = ft.Row([ft.Text(text, color=color, font_family="Consolas", expand=True)])
        self.chat_history.controls.append(row)
        try: self.chat_history.update()
        except Exception: pass

    def remove_message(self, msg_id: int):
        target_key = f"msg_{msg_id}"
        for ctrl in self.chat_history.controls:
            if getattr(ctrl, "key", None) == target_key:
                self.chat_history.controls.remove(ctrl)
                try: self.chat_history.update()
                except Exception: pass
                break

    def update_message(self, msg_id: int, sender: str, text: str, timestamp: float, file_name: str = None, updated_at: float = None, is_read: bool = False, local_path: str = None):
        target_key = f"msg_{msg_id}"
        for i, ctrl in enumerate(self.chat_history.controls):
            if getattr(ctrl, "key", None) == target_key:
                l_path = local_path or getattr(ctrl, "local_path", None)
                new_row = self._create_message_row(sender, text, timestamp, msg_id, file_name, l_path, updated_at, is_read)
                self.chat_history.controls[i] = new_row
                try:
                    self.chat_history.update()
                except Exception:
                    pass
                break

    def mark_own_messages_as_read(self):
        changed = False
        for i, ctrl in enumerate(self.chat_history.controls):
            if getattr(ctrl, "sender", None) == self.current_username and not getattr(ctrl, "is_read", False):
                sender = getattr(ctrl, "sender", "")
                text = getattr(ctrl, "text", "")
                timestamp = getattr(ctrl, "timestamp", 0)
                msg_id = getattr(ctrl, "msg_id", None)
                file_name = getattr(ctrl, "file_name", None)
                local_path = getattr(ctrl, "local_path", None)
                updated_at = getattr(ctrl, "updated_at", None)
                
                new_row = self._create_message_row(
                    sender, text, timestamp, msg_id, file_name, local_path, updated_at, is_read=True
                )
                self.chat_history.controls[i] = new_row
                changed = True
        if changed:
            try:
                self.chat_history.update()
            except Exception:
                pass

    def _handle_scroll(self, e):
        try:
            if float(e.pixels) < 50:
                self.on_load_more_history()
        except Exception:
            pass

    def _create_message_row(self, sender: str, text: str, timestamp: float, msg_id: int = None, file_name: str = None, local_path: str = None, updated_at: float = None, is_read: bool = False):
        ts = datetime.fromtimestamp(timestamp).strftime('%H:%M')
        is_own = (sender == self.current_username)
        content = None

        img_exts = ['png', 'jpg', 'jpeg', 'gif', 'webp']
        vid_exts = ['mp4', 'mov', 'avi', 'mkv', 'webm']
        audio_exts = ['mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac']

        # Маркер измененного сообщения
        edited_label = " (изменено)" if updated_at else ""

        # Настройка цветов пузырей в стиле мессенджеров
        if is_own:
            bubble_color = "#2b5278"  # Premium dark blue-gray
            text_color = ft.Colors.WHITE
            border_radius = ft.BorderRadius.only(top_left=12, top_right=12, bottom_left=12, bottom_right=2)
            main_alignment = ft.MainAxisAlignment.END
        else:
            bubble_color = "#262626"  # Dark gray
            text_color = ft.Colors.GREY_100
            border_radius = ft.BorderRadius.only(top_left=12, top_right=12, bottom_left=2, bottom_right=12)
            main_alignment = ft.MainAxisAlignment.START

        if file_name:
            ext = file_name.lower().split('.')[-1]

            # 1. Фото или Видео
            if ext in img_exts or ext in vid_exts:
                is_video = ext in vid_exts
                media_url = self.on_get_media_url(msg_id)
                thumb = ft.Image(src=media_url, width=200, height=200, fit=ft.BoxFit.COVER, border_radius=10)

                if is_video:
                    thumb = ft.Stack([
                        thumb,
                        ft.Container(content=ft.Icon(ft.Icons.PLAY_CIRCLE_FILL, size=40, color=ft.Colors.WHITE70),
                                     alignment=ft.Alignment.CENTER, width=200, height=200)
                    ])

                content = ft.Container(
                    content=thumb,
                    on_click=lambda e, m_url=media_url, is_v=is_video, fname=file_name: self.on_open_media(m_url, is_v, fname),
                    tooltip="Кликните для просмотра",
                    border_radius=10
                )

            # 2. Аудио-файл
            elif ext in audio_exts:
                media_url = self.on_get_media_url(msg_id)
                play_btn = ft.IconButton(icon=ft.Icons.PLAY_ARROW, icon_color=ft.Colors.BLUE, tooltip="Воспроизвести")
                audio_player = None

                def play_pause_click(e, btn=play_btn, url=media_url):
                    nonlocal audio_player
                    if not audio_player:
                        def on_state_changed(ev, b=btn):
                            if ev.data == "completed":
                                b.icon = ft.Icons.PLAY_ARROW
                                try: b.update()
                                except Exception: pass

                        audio_player = ft.Audio(src=url, on_state_changed=on_state_changed)
                        self.page.overlay.append(audio_player)
                        self.page.update()

                    if btn.icon == ft.Icons.PLAY_ARROW:
                        btn.icon = ft.Icons.PAUSE
                        btn.update()
                        audio_player.play()
                    else:
                        btn.icon = ft.Icons.PLAY_ARROW
                        btn.update()
                        audio_player.pause()

                play_btn.on_click = play_pause_click

                content = ft.Row([
                    play_btn,
                    ft.Text(f"🎵 {file_name}", color=ft.Colors.BLUE_200, italic=True, size=13, expand=True)
                ], spacing=10, tight=True)

            # 3. Любой другой файл (Документ)
            else:
                import os
                is_downloaded = False
                if local_path:
                    try:
                        if os.path.exists(local_path):
                            is_downloaded = True
                    except Exception:
                        pass

                icon_color = ft.Colors.BLUE_400 if is_downloaded else ft.Colors.GREY_400
                status_text = "Открыть файл" if is_downloaded else "Нажмите, чтобы скачать"

                def on_doc_click(e, is_dl=is_downloaded, path=local_path, mid=msg_id, fname=file_name):
                    if is_dl and path:
                        open_file_in_default_app(path)
                    else:
                        self.on_download_file(mid, fname)

                content = ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.INSERT_DRIVE_FILE, size=24, color=ft.Colors.WHITE),
                            bgcolor=ft.Colors.BLUE_900 if is_downloaded else ft.Colors.GREY_800,
                            padding=10,
                            border_radius=8
                        ),
                        ft.Column([
                            ft.Text(file_name, color=text_color, weight="bold", size=13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(status_text, color=ft.Colors.GREY_400, size=11)
                        ], spacing=2, tight=True, expand=True)
                    ], spacing=10, tight=True),
                    on_click=on_doc_click,
                    padding=5,
                    border_radius=8,
                    tooltip=status_text
                )
        else:
            # 4. Текстовое сообщение
            content = ft.Text(text, color=text_color, size=13, selectable=True)

        # Контекстное меню "Три точки" (PopupMenuButton)
        menu_items = []
        if not file_name:
            menu_items.append(
                ft.PopupMenuItem(icon=ft.Icons.COPY, content=ft.Text("Копировать"), on_click=lambda e, t=text: self.on_copy_message(t))
            )
        else:
            menu_items.append(
                ft.PopupMenuItem(icon=ft.Icons.DOWNLOAD, content=ft.Text("Скачать"), on_click=lambda e, m=msg_id, f=file_name: self.on_download_file(m, f))
            )

        if is_own and msg_id:
            menu_items.append(
                ft.PopupMenuItem(icon=ft.Icons.EDIT, content=ft.Text("Редактировать"), on_click=lambda e, m=msg_id, t=text, f=file_name: self.on_edit_message(m, t, f))
            )
            menu_items.append(
                ft.PopupMenuItem(icon=ft.Icons.DELETE_OUTLINE, content=ft.Text("Удалить"), on_click=lambda e, m=msg_id: self.on_delete_message(m))
            )

        if updated_at:
            edit_ts = datetime.fromtimestamp(updated_at).strftime('%H:%M')
            menu_items.append(ft.PopupMenuItem(content=ft.Text(f"Изменено: {edit_ts}"), disabled=True))

        actions_menu = ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT,
            icon_size=18,
            icon_color=ft.Colors.GREY_600,
            items=menu_items,
            tooltip="Действия"
        )

        show_finder_btn = None
        if file_name and local_path:
            import os
            try:
                if os.path.exists(local_path):
                    import platform
                    system = platform.system()
                    if system == "Darwin":
                        btn_label = "Показать в Finder"
                    elif system == "Windows":
                        btn_label = "Показать в проводнике"
                    else:
                        btn_label = "Показать в папке"

                    def on_show_click(e, path=local_path):
                        import subprocess
                        import platform
                        try:
                            sys_name = platform.system()
                            if sys_name == "Darwin":
                                subprocess.run(["open", "-R", path])
                            elif sys_name == "Windows":
                                subprocess.run(["explorer", "/select,", os.path.normpath(path)])
                            else:
                                subprocess.run(["xdg-open", os.path.dirname(path)])
                        except Exception as err:
                            pass

                    show_finder_btn = ft.TextButton(
                        text=btn_label,
                        icon=ft.Icons.FOLDER_OPEN,
                        icon_color=ft.Colors.BLUE_300,
                        style=ft.ButtonStyle(
                            color=ft.Colors.BLUE_300,
                            text_style=ft.TextStyle(size=11, weight="bold"),
                        ),
                        on_click=on_show_click
                    )
            except Exception:
                pass

        # Собираем элементы внутри пузыря (bubble)
        bubble_items = []
        if not is_own:
            # Имя отправителя в групповых переписках
            bubble_items.append(
                ft.Text(sender, color=ft.Colors.BLUE_300, weight="bold", size=11)
            )

        bubble_items.append(content)

        if show_finder_btn:
            bubble_items.append(show_finder_btn)

        # Галочки и время отправки
        tick_str = ""
        tick_color = ft.Colors.GREY_500
        if is_own:
            tick_str = " ✓✓" if is_read else " ✓"
            tick_color = ft.Colors.BLUE_300 if is_read else ft.Colors.GREY_500

        footer = ft.Row([
            ft.Text(f"{ts}{edited_label}", color=ft.Colors.GREY_500, size=9),
            ft.Text(tick_str, color=tick_color, size=9, weight="bold")
        ], alignment=ft.MainAxisAlignment.END, spacing=3)

        bubble_items.append(footer)

        # Контейнер самого пузыря сообщения
        bubble = ft.Container(
            content=ft.Column(bubble_items, spacing=4, tight=True),
            bgcolor=bubble_color,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border_radius=border_radius,
            expand=True,
        )

        # Выравнивание строки: свои справа, чужие слева
        if is_own:
            row_controls = [actions_menu, bubble]
        else:
            row_controls = [bubble, actions_menu]

        row = ft.Row(
            controls=row_controls,
            alignment=main_alignment,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        # Обертка контейнером для отступа от краев (чтобы не перекрывалось скроллбаром)
        if is_own:
            outer_padding = ft.Padding(left=50, top=2, right=15, bottom=2)
        else:
            outer_padding = ft.Padding(left=15, top=2, right=50, bottom=2)

        container = ft.Container(
            content=row,
            padding=outer_padding,
            key=f"msg_{msg_id}" if msg_id else None
        )
        container.msg_id = msg_id
        container.sender = sender
        container.text = text
        container.timestamp = timestamp
        container.file_name = file_name
        container.local_path = local_path
        container.updated_at = updated_at
        container.is_read = is_read
        return container

    def add_message(self, sender: str, text: str, timestamp: float, msg_id: int = None, file_name: str = None, local_path: str = None, updated_at: float = None, is_read: bool = False):
        row = self._create_message_row(sender, text, timestamp, msg_id, file_name, local_path, updated_at, is_read)
        self.chat_history.controls.append(row)
        try:
            self.chat_history.update()
        except Exception:
            pass

    def prepend_messages(self, messages: list):
        was_auto = self.chat_history.auto_scroll
        self.chat_history.auto_scroll = False

        rows = []
        for msg in messages:
            row = self._create_message_row(
                msg['sender'],
                msg.get('text', ''),
                msg['timestamp'],
                msg.get('id'),
                msg.get('file_name'),
                msg.get('local_path'),
                msg.get('updated_at'),
                msg.get('is_read', False)
            )
            rows.append(row)

        self.chat_history.controls = rows + self.chat_history.controls

        try:
            self.chat_history.update()
            self.chat_history.auto_scroll = was_auto
            self.chat_history.update()
        except Exception:
            pass