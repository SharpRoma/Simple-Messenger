import flet as ft

class BaseController:
    def __init__(self, page: ft.Page, app_controller):
        self.page = page
        self.app = app_controller
