#!/bin/bash

# Останавливаем скрипт при любой ошибке
set -e

echo "Начинаем сборку Simple Messenger для macOS..."

# 1. Проверка наличия иконки
if [ ! -f "app_icon.png" ]; then
    echo "ОШИБКА: Файл app_icon.png не найден в корне проекта!"
    echo "Пожалуйста, положите картинку с иконкой и попробуйте снова."
    exit 1
fi

# 2. Конвертация иконки в маковский формат
echo "Подготовка иконок..."
sips -s format icns app_icon.png --out AppIcon.icns > /dev/null

# 3. Очистка старого кэша
echo "Удаление старых сборок..."
rm -rf build dist

# 4. Сборка через Flet
echo "Упаковка Python-кода (flet pack)..."
flet pack client/main.py --name "SimpleMessenger" --icon app_icon.png

# 5. Применение патчей macOS
echo "Применение патчей macOS (лечение 'болезни двух матрешек')..."
APP_PATH="dist/SimpleMessenger.app"

# Прячем Питон-обертку из Dock
plutil -insert LSUIElement -bool true "$APP_PATH/Contents/Info.plist"

# Ищем внутренний движок
FLET_APP=$(find "$APP_PATH" -type d -name "flet.app" -o -name "Flet.app" | head -n 1)

# Подменяем иконку и системные имена
cp AppIcon.icns "$FLET_APP/Contents/Resources/AppIcon.icns"
plutil -replace CFBundleIdentifier -string "com.simplemessenger.app.inner" "$FLET_APP/Contents/Info.plist"
plutil -replace CFBundleName -string "Simple Messenger" "$FLET_APP/Contents/Info.plist"
plutil -replace CFBundleDisplayName -string "Simple Messenger" "$FLET_APP/Contents/Info.plist"

# Удаляем жесткий английский перевод (из-за которого писалось flet)
rm -f "$FLET_APP/Contents/Resources/en.lproj/InfoPlist.strings"

# 6. Подпись приложения (Bypass macOS Gatekeeper)
echo "Переподписание приложения..."
codesign --force --deep --sign - "$FLET_APP" > /dev/null 2>&1
codesign --force --deep --sign - "$APP_PATH" > /dev/null 2>&1

# 7. Обновление системного кэша
echo "Обновление кэша Dock и LaunchServices..."
/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f "$APP_PATH"
killall Dock

echo "СБОРКА УСПЕШНО ЗАВЕРШЕНА!"
echo "Ваше приложение готово: dist/SimpleMessenger.app"