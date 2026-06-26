@echo off
chcp 65001 > nul

set ORIGINAL_DIR=%cd%

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

:: Фикс бага 32-битного CMake (File System Redirector)
:: CMake (32-bit) ищет файлы в SysWOW64 вместо System32. Скопируем файл туда, чтобы CMake его нашёл.
if exist "C:\Windows\System32\vcruntime140_1.dll" (
    if not exist "C:\Windows\SysWOW64\vcruntime140_1.dll" (
        echo Фикс для CMake: копирование vcruntime140_1.dll в SysWOW64...
        copy "C:\Windows\System32\vcruntime140_1.dll" "C:\Windows\SysWOW64\vcruntime140_1.dll" > nul
    )
)

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

set BUILD_DIR=C:\Users\Public\MessengerClient_%RANDOM%

echo Удаление старых сборок...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "client\build" rmdir /s /q "client\build"
if exist "*.spec" del /q "*.spec"
if exist "*.ico" del /q "*.ico"

echo Копирование исходников в ASCII-директорию (папка src) для сборки...
mkdir "%BUILD_DIR%\src"
xcopy client "%BUILD_DIR%\src" /E /I /H /Y /Q > nul

:: Заходим во временную ASCII папку
cd /d "%BUILD_DIR%"

echo Сборка нативного приложения (flet build)...
call "%ORIGINAL_DIR%\.venv\Scripts\flet" build windows src -v --project "SimpleMessenger" --module-name main --compile-app --icon "src\assets\icon.png" --build-version "%APP_VERSION%" --product "Simple Messenger" --copyright "SharpRoma" -o dist

:: Возвращаемся в оригинальный корень проекта
cd /d "%ORIGINAL_DIR%"

if not exist "%BUILD_DIR%\dist\SimpleMessenger.exe" (
    echo ОШИБКА СБОРКИ: Файл SimpleMessenger.exe не был создан.
    echo Не удаляем временную папку %BUILD_DIR% для отладки.
    pause
    exit /b 1
)

:: Переносим скомпилированные файлы на место папки dist
if exist "dist" rmdir /s /q "dist"
move "%BUILD_DIR%\dist" "dist" > nul

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
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"

echo.
echo СБОРКА УСПЕШНО ЗАВЕРШЕНА!
pause