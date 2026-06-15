@echo off
:: Включаем поддержку кириллицы
chcp 65001 > nul

:: АВТОМАТИКА: Переходим в корень проекта
cd /d "%~dp0\.."

echo Начинаем сборку Simple Messenger для Windows...

set ICON_PATH=client\assets\icon.png

if not exist "%ICON_PATH%" (
    echo ОШИБКА: Файл %ICON_PATH% не найден!
    pause
    exit /b 1
)

:: Автоматически активируем виртуальное окружение
if exist ".venv\Scripts\activate.bat" (
    echo Активация виртуального окружения...
    call .venv\Scripts\activate.bat
) else (
    echo ОШИБКА: Папка .venv не найдена! Убедитесь, что вы создали окружение.
    pause
    exit /b 1
)

echo Удаление старых сборок...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"

echo Упаковка Python-кода (flet pack)...
flet pack client\main.py --name "SimpleMessenger" --icon "%ICON_PATH%" --product-name "Simple Messenger" --product-version "1.1.0" --copyright "Simple Messenger"

if not exist "dist\SimpleMessenger.exe" (
    echo ОШИБКА СБОРКИ: Файл SimpleMessenger.exe не был создан. Посмотрите ошибки выше!
    pause
    exit /b 1
)

:: --- ИНТЕГРАЦИЯ INNO SETUP ---
echo.
echo Поиск Inno Setup для создания установщика...
set ISCC_PATH="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC_PATH% set ISCC_PATH="%ProgramFiles%\Inno Setup 6\ISCC.exe"

if exist %ISCC_PATH% (
    echo Компиляция SimpleMessenger_Setup.exe...
    %ISCC_PATH% scripts\installer.iss > nul
    echo Установщик успешно создан!
) else (
    echo.
    echo ВНИМАНИЕ: Компилятор Inno Setup 6 не найден!
    echo Установщик (Setup.exe) не был собран. Обычный .exe файл доступен в папке dist.
    echo Скачать Inno Setup: https://jrsoftware.org/isdl.php
)

:: ФИНАЛЬНАЯ УБОРКА МУСОРА
echo.
echo Очистка временных файлов сборки...
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"

echo.
echo СБОРКА УСПЕШНО ЗАВЕРШЕНА!
echo Результаты лежат в папке: dist\
pause