import pytest
from unittest.mock import patch, MagicMock
from system.utils import open_file_in_default_app, open_url_in_browser, open_folder_and_select_file


@patch("system.utils.platform.system")
@patch("system.utils.subprocess.run")
def test_open_file_in_default_app_darwin(mock_run, mock_system):
    mock_system.return_value = "Darwin"
    open_file_in_default_app("some/path/file.txt")
    mock_run.assert_called_once_with(["open", "some/path/file.txt"])


@patch("system.utils.platform.system")
@patch("system.utils.subprocess.run")
def test_open_file_in_default_app_linux(mock_run, mock_system):
    mock_system.return_value = "Linux"
    open_file_in_default_app("some/path/file.txt")
    mock_run.assert_called_once_with(["xdg-open", "some/path/file.txt"])


@patch("system.utils.platform.system")
@patch("system.utils.os.startfile", create=True)
def test_open_file_in_default_app_windows(mock_startfile, mock_system):
    mock_system.return_value = "Windows"
    open_file_in_default_app("some/path/file.txt")
    mock_startfile.assert_called_once_with("some/path/file.txt")


@patch("system.utils.webbrowser.open")
def test_open_url_in_browser(mock_webbrowser_open):
    open_url_in_browser("https://google.com")
    mock_webbrowser_open.assert_called_once_with("https://google.com")


@patch("system.utils.platform.system")
@patch("system.utils.subprocess.run")
def test_open_folder_and_select_file_darwin(mock_run, mock_system):
    mock_system.return_value = "Darwin"
    open_folder_and_select_file("some/path/file.txt")
    mock_run.assert_called_once_with(["open", "-R", "some/path/file.txt"])


@patch("system.utils.platform.system")
@patch("system.utils.subprocess.run")
def test_open_folder_and_select_file_linux(mock_run, mock_system):
    mock_system.return_value = "Linux"
    open_folder_and_select_file("some/path/file.txt")
    mock_run.assert_called_once_with(["xdg-open", "some/path"])
