#!/bin/bash

# Останавливаем скрипт при любой ошибке
set -e

# Переходим в папку client
cd "$(dirname "$0")/../client"

# Активация виртуального окружения
VENV_DIR="../.venv"
if [ -d "$VENV_DIR" ]; then
    echo "Активация виртуального окружения..."
    source "$VENV_DIR/bin/activate"
else
    echo "ВНИМАНИЕ: Папка .venv не найдена в корне проекта. Сборка будет выполнена в текущем окружении."
fi

# Проверка наличия websockets и при необходимости установка зависимостей
if python3 -c "import websockets" 2>/dev/null; then
    echo "Зависимости найдены в виртуальном окружении."
else
    echo "ВНИМАНИЕ: Зависимости не найдены. Установка из requirements.txt..."
    python3 -m pip install -r requirements.txt
fi

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

# Нативная компиляция для архитектуры текущего хоста (arm64 или x64)
# Это предотвращает ошибки компиляции библиотеки cryptography из-за несовместимости архитектур
HOST_ARCH=$(uname -m)
if [ "$HOST_ARCH" = "arm64" ]; then
    TARGET_ARCH="arm64"
elif [ "$HOST_ARCH" = "x86_64" ]; then
    TARGET_ARCH="x64"
else
    TARGET_ARCH="arm64 x64"
fi

echo "Используется Flet Build для архитектуры: $TARGET_ARCH..."
flet build macos --build-version "$APP_VERSION" --arch $TARGET_ARCH

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