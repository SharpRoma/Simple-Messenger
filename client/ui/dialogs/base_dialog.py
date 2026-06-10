import flet as ft
import asyncio

class BaseDialog:
    def __init__(self, page: ft.Page):
        self.page = page
        self.dialog = None  # Сюда наследники положат ft.AlertDialog

    def show(self):
        if self.dialog:
            self.page.overlay.append(self.dialog)
            self.dialog.open = True
            self.page.update()

    def close(self):
        if self.dialog:
            self.dialog.open = False
            self.page.update()

            # Плавное удаление из памяти после анимации
            async def remove_later():
                await asyncio.sleep(0.2)
                if self.dialog in self.page.overlay:
                    self.page.overlay.remove(self.dialog)
                    self.page.update()

            self.page.run_task(remove_later)