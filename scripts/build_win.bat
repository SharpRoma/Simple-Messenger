@echo off
chcp 65001 > nul
cd /d "%~dp0\.."

echo Начинаем сборку Simple Messenger для Windows...

set ICON_PATH=client\assets\icon.png
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
if exist "*.spec" del /q "*.spec"
if exist "*.ico" del /q "*.ico"

echo Упаковка Python-кода (flet pack)...
:: Вызываем flet.exe напрямую из виртуального окружения и добавляем websockets в скрытые импорты
call .venv\Scripts\flet pack client\main.py --name "SimpleMessenger" --icon "%ICON_PATH%" --product-name "Simple Messenger" --product-version "%APP_VERSION%" --copyright "Simple Messenger" --add-data "client\assets;assets" --hidden-import websockets

if not exist "dist\SimpleMessenger.exe" (
    echo ОШИБКА СБОРКИ: Файл SimpleMessenger.exe не был создан.
    pause
    exit /b 1
)

:: --- ИНТЕГРАЦИЯ INNO SETUP ---
echo.
set ISCC_PATH="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC_PATH% set ISCC_PATH="%ProgramFiles%\Inno Setup 6\ISCC.exe"

if exist %ISCC_PATH% (
    echo Компиляция SimpleMessenger_Setup_v%APP_VERSION%.exe...
    :: Передаем версию в .iss файл через параметр /DAppVersion
    %ISCC_PATH% /O"dist" /DAppVersion="%APP_VERSION%" scripts\installer.iss > nul
    echo Установщик успешно создан!
    echo Удаление исходного .exe файла...
    if exist "dist\SimpleMessenger.exe" del /q "dist\SimpleMessenger.exe"
) else (
    echo ВНИМАНИЕ: Inno Setup 6 не найден!
)

:: ФИНАЛЬНАЯ УБОРКА МУСОРА
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"
if exist "*.ico" del /q "*.ico"

echo.
echo СБОРКА УСПЕШНО ЗАВЕРШЕНА!
pause