@echo off
:: Включаем поддержку кириллицы
chcp 65001 > nul

echo Начинаем сборку Simple Messenger для Windows...

if not exist "app_icon.png" (
    echo ОШИБКА: Файл app_icon.png не найден в корне проекта!
    pause
    exit /b 1
)

:: Автоматически активируем виртуальное окружение!
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
:: Используем обратный слеш (для Windows)
flet pack client\main.py --name "SimpleMessenger" --icon app_icon.png

:: Проверяем, появился ли файл в папке dist
if not exist "dist\SimpleMessenger.exe" (
    echo ОШИБКА СБОРКИ: Файл SimpleMessenger.exe не был создан. Посмотрите ошибки выше!
    pause
    exit /b 1
)

echo Очистка временных файлов сборки...
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"

echo.
echo СБОРКА УСПЕШНО ЗАВЕРШЕНА!
echo Ваше приложение готово в папке: dist\SimpleMessenger.exe
pause