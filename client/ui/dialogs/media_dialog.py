import flet as ft
from .base_dialog import BaseDialog


class MediaDialog(BaseDialog):
    def __init__(self, page: ft.Page, media_url: str, is_video: bool, filename: str):
        super().__init__(page)

        if is_video:
            # Встроенный видеоплеер Flet
            content = ft.Video(
                expand=True,
                playlist=[ft.VideoMedia(media_url)],
                autoplay=True,
                show_controls=True
            )
        else:
            # Интерактивный просмотрщик для фото
            content = ft.InteractiveViewer(
                min_scale=0.5,
                max_scale=5.0,  # Можно приблизить в 5 раз
                boundary_margin=ft.Margin.all(0),
                content=ft.Image(src=media_url, fit=ft.BoxFit.CONTAIN)
            )

        self.dialog = ft.AlertDialog(
            title=ft.Text(filename, weight="bold"),
            # Задаем размер модального окна (800x600)
            content=ft.Container(content=content, width=800, height=600, alignment=ft.Alignment.CENTER),
            actions=[ft.TextButton("Закрыть", on_click=lambda e: self.close())],
            title_padding=15,
            content_padding=10,
            actions_padding=10
        )