@echo off
chcp 65001 > nul
cd /d "%~dp0\.."
set ORIGINAL_DIR=%cd%

:: Обход ошибки путей с кириллицей (например, C:\Users\Администратор) при установке/работе Flutter SDK.
:: Временно перенаправляем домашний профиль в стандартную ASCII-директорию C:\Users\Public.
set USERPROFILE=C:\Users\Public
set HOMEPATH=\Users\Public
set HOMEDRIVE=C:
set APPDATA=C:\Users\Public\AppData\Roaming
set LOCALAPPDATA=C:\Users\Public\AppData\Local

if not exist "%APPDATA%" mkdir "%APPDATA%"
if not exist "%LOCALAPPDATA%" mkdir "%LOCALAPPDATA%"
if not exist "C:\Users\Public\Documents" mkdir "C:\Users\Public\Documents"

echo Начинаем сборку Simple Messenger для Windows...

:: Завершаем любые работающие процессы приложения, чтобы избежать блокировки файлов при перезаписи
echo Закрытие запущенных копий приложения...
taskkill /F /IM SimpleMessenger.exe >nul 2>nul
taskkill /F /IM flet.exe >nul 2>nul
taskkill /F /IM flet_desktop.exe >nul 2>nul

set ICON_PATH=client\assets\icon.ico
if not exist "%ICON_PATH%" (
    echo ОШИБКА: Файл %ICON_PATH% не найден!
    pause
    exit /b 1
)

:: --- ЧИТАЕМ ВЕРСИЮ ИЗ CONFIG.PY ---
for /f "tokens=2 delims==" %%a in ('findstr /B "APP_VERSION" client\config.py') do set RAW_VERSION=%%a
:: Очищаем от кавычек и пробелов
set APP_VERSION=%RAW_VERSION:"=%
set APP_VERSION=%APP_VERSION: =%
echo Обнаружена версия проекта: %APP_VERSION%

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ОШИБКА: Папка .venv не найдена!
    pause
    exit /b 1
)

:: Проверяем наличие websockets и при необходимости устанавливаем зависимости
python -c "import websockets" 2>nul
if %errorlevel% neq 0 (
    echo ВНИМАНИЕ: Зависимости не найдены в виртуальном окружении. Установка...
    python -m pip install -r client/requirements.txt
)

echo Удаление старых сборок...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "client\build" rmdir /s /q "client\build"
if exist "*.spec" del /q "*.spec"
if exist "*.ico" del /q "*.ico"
if exist "C:\Users\Public\MessengerClient" rmdir /s /q "C:\Users\Public\MessengerClient"

echo Копирование исходников в ASCII-директорию для сборки...
xcopy client C:\Users\Public\MessengerClient /E /I /H /Y /Q > nul

:: Заходим во временную ASCII папку
cd /d "C:\Users\Public\MessengerClient"

echo Сборка нативного приложения (flet build)...
:: Вызываем flet build из оригинального виртуального окружения
call "%ORIGINAL_DIR%\.venv\Scripts\flet" build windows --project "SimpleMessenger" --build-version "%APP_VERSION%" --product "Simple Messenger" --copyright "SharpRoma" -o dist

:: Возвращаемся в оригинальный корень проекта
cd /d "%ORIGINAL_DIR%"

if not exist "C:\Users\Public\MessengerClient\dist\SimpleMessenger.exe" (
    echo ОШИБКА СБОРКИ: Файл SimpleMessenger.exe не был создан.
    if exist "C:\Users\Public\MessengerClient" rmdir /s /q "C:\Users\Public\MessengerClient"
    pause
    exit /b 1
)

:: Переносим скомпилированные файлы на место папки dist
if exist "dist" rmdir /s /q "dist"
move "C:\Users\Public\MessengerClient\dist" "dist" > nul

:: --- ИНТЕГРАЦИЯ INNO SETUP ---
echo.
set ISCC_PATH="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC_PATH% set ISCC_PATH="%ProgramFiles%\Inno Setup 6\ISCC.exe"

if exist %ISCC_PATH% (
    echo Компиляция SimpleMessenger_Setup_v%APP_VERSION%.exe...
    :: Передаем версию в .iss файл через параметр /DAppVersion
    %ISCC_PATH% /O"dist" /DAppVersion="%APP_VERSION%" scripts\installer.iss > nul
    echo Установщик успешно создан!
    echo Очистка временных файлов сборки в dist...
    :: Сохраняем готовый установщик во временный файл в корне
    move "dist\SimpleMessenger_Setup_v%APP_VERSION%.exe" "SimpleMessenger_Setup_v%APP_VERSION%.exe" > nul
    :: Удаляем папку dist со всеми DLL и ресурсами
    rmdir /s /q "dist"
    :: Пересоздаем чистую dist и возвращаем установщик на место
    mkdir "dist"
    move "SimpleMessenger_Setup_v%APP_VERSION%.exe" "dist\SimpleMessenger_Setup_v%APP_VERSION%.exe" > nul
) else (
    echo ВНИМАНИЕ: Inno Setup 6 не найден!
)

:: ФИНАЛЬНАЯ УБОРКА МУСОРА
if exist "build" rmdir /s /q "build"
if exist "client\build" rmdir /s /q "client\build"
if exist "*.spec" del /q "*.spec"
if exist "*.ico" del /q "*.ico"
if exist "C:\Users\Public\MessengerClient" rmdir /s /q "C:\Users\Public\MessengerClient"

echo.
echo СБОРКА УСПЕШНО ЗАВЕРШЕНА!
pause