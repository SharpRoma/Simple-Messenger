@echo off
chcp 65001 > nul

:: Переходим в короткий (8.3) путь скрипта, чтобы избавиться от кириллицы в рабочем каталоге проекта!
for %%I in ("%~dp0\..") do set PROJECT_DIR=%%~sI
cd /d "%PROJECT_DIR%"

:: Обход ошибки путей с кириллицей (например, C:\Users\Администратор) при работе Flutter SDK.
:: Используем встроенные короткие пути Windows (8.3), которые содержат только ASCII.
for %%I in ("%USERPROFILE%") do set USERPROFILE=%%~sI
for %%I in ("%APPDATA%") do set APPDATA=%%~sI
for %%I in ("%LOCALAPPDATA%") do set LOCALAPPDATA=%%~sI
for %%I in ("%HOMEPATH%") do set HOMEPATH=%%~sI

echo Начинаем сборку Simple Messenger для Windows...

:: Завершаем любые работающие процессы приложения
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

:: Проверяем наличие зависимостей
python -c "import websockets" 2>nul
if %errorlevel% neq 0 (
    echo ВНИМАНИЕ: Зависимости не найдены. Установка...
    python -m pip install -r client/requirements.txt
)

echo Удаление старых сборок...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "client\build" rmdir /s /q "client\build"
if exist "*.spec" del /q "*.spec"
if exist "*.ico" del /q "*.ico"

:: Заходим в папку client для сборки
cd client

echo Сборка нативного приложения (flet build)...
call ..\.venv\Scripts\flet build windows --project "SimpleMessenger" --build-version "%APP_VERSION%" --product "Simple Messenger" --copyright "SharpRoma" -o ..\dist

cd ..

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
    %ISCC_PATH% /O"dist" /DAppVersion="%APP_VERSION%" scripts\installer.iss > nul
    echo Установщик успешно создан!
    
    :: Перемещаем установщик в корень и очищаем dist
    move "dist\SimpleMessenger_Setup_v%APP_VERSION%.exe" "SimpleMessenger_Setup_v%APP_VERSION%.exe" > nul
    rmdir /s /q "dist"
    mkdir "dist"
    move "SimpleMessenger_Setup_v%APP_VERSION%.exe" "dist\SimpleMessenger_Setup_v%APP_VERSION%.exe" > nul
) else (
    echo ВНИМАНИЕ: Inno Setup 6 не найден!
)

:: ФИНАЛЬНАЯ УБОРКА МУСОРА
if exist "build" rmdir /s /q "build"
if exist "client\build" rmdir /s /q "client\build"

echo.
echo СБОРКА УСПЕШНО ЗАВЕРШЕНА!
pause