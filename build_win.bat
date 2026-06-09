@echo off
:: Включаем поддержку русского языка в консоли Windows
chcp 65001 > nul

echo Начинаем сборку Simple Messenger для Windows...

:: 1. Проверка наличия иконки
if not exist "app_icon.png" (
    echo ОШИБКА: Файл app_icon.png не найден в корне проекта!
    echo Пожалуйста, положите картинку с иконкой и попробуйте снова.
    pause
    exit /b 1
)

:: 2. Очистка старого кэша
echo 🧹 Удаление старых сборок...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"

:: 3. Сборка через Flet
echo Упаковка Python-кода (flet pack)...
:: Flet на Windows сам конвертирует .png в формат .ico, нам не нужно делать это вручную!
flet pack client/main.py --name "SimpleMessenger" --icon app_icon.png

:: 4. Финальная уборка мусора
echo Очистка временных файлов сборки...
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"

echo.
echo СБОРКА УСПЕШНО ЗАВЕРШЕНА!
echo Ваше приложение готово в папке: dist\SimpleMessenger.exe
pause