#!/bin/bash

# Останавливаем скрипт при любой ошибке
set -e

# Переходим в папку client
cd "$(dirname "$0")/../client"

echo "Начинаем нативную сборку Simple Messenger для macOS..."

# --- ЧИТАЕМ ВЕРСИЮ ИЗ CONFIG.PY ---
# Используем grep и awk для извлечения значения в кавычках
APP_VERSION=$(grep 'APP_VERSION' config.py | awk -F '"' '{print $2}')
if [ -z "$APP_VERSION" ]; then
    APP_VERSION="1.0.0"
fi
echo "Обнаружена версия проекта: $APP_VERSION"

# Очистка
rm -rf build ../dist
mkdir -p ../dist

# Нативная компиляция
echo "Используется Flet Build..."
flet build macos --build-version "$APP_VERSION"

APP_PATH=$(find build/macos -type d -name "*.app" | head -n 1)
FINAL_APP_PATH="../dist/SimpleMessenger.app"

if [ -n "$APP_PATH" ]; then
    echo "Копирование приложения..."
    ditto "$APP_PATH" "$FINAL_APP_PATH"

    # Жестко прописываем версию в Info.plist (чтобы macOS знала, какая это версия)
    # Это включит нативную защиту Finder от установки старых версий поверх новых
    plutil -replace CFBundleShortVersionString -string "$APP_VERSION" "$FINAL_APP_PATH/Contents/Info.plist"
    plutil -replace CFBundleVersion -string "$APP_VERSION" "$FINAL_APP_PATH/Contents/Info.plist"

    # --- СОЗДАНИЕ УСТАНОВОЧНОГО ОБРАЗА (.DMG) ---
    echo "Создание установочного образа (.dmg)..."
    DMG_NAME="../dist/SimpleMessenger_Setup_v${APP_VERSION}.dmg"

    # Используем встроенную в macOS утилиту hdiutil (без сторонних программ!)
    hdiutil create -volname "Simple Messenger" -srcfolder "$FINAL_APP_PATH" -ov -format UDZO "$DMG_NAME" > /dev/null

    # --- УДАЛЯЕМ ИСХОДНЫЙ .APP ---
    echo "Очистка временных файлов (удаление исходного .app)..."
    rm -rf "$FINAL_APP_PATH"

    # Уборка мусора
    rm -rf build

    echo ""
    echo "СБОРКА УСПЕШНО ЗАВЕРШЕНА!"
    echo "Приложение: dist/SimpleMessenger.app"
    echo "Установочный образ: dist/SimpleMessenger_v${APP_VERSION}.dmg"
else
    echo "ОШИБКА: Приложение не было собрано. Проверьте логи выше."
    exit 1
fi