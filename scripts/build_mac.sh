#!/bin/bash

# Останавливаем скрипт при любой ошибке
set -e

# Переходим в папку client (именно там лежат assets, main.py и requirements.txt)
cd "$(dirname "$0")/../client"

echo "Начинаем нативную сборку Simple Messenger для macOS..."
echo "Используется Flet Build (создание монолитного приложения)..."

# Очистка
rm -rf build ../dist

# 🚀 Нативная компиляция!
# ВАЖНО: При самом первом запуске эта команда может работать 2-3 минуты,
# так как она автоматически скачивает Flutter SDK от Google.
flet build macos

echo "Перемещение готового приложения в папку dist..."
mkdir -p ../dist
APP_PATH=$(find build/macos -type d -name "*.app" | head -n 1)

if [ -n "$APP_PATH" ]; then
    cp -r "$APP_PATH" ../dist/SimpleMessenger.app
    rm -rf build
    echo "СБОРКА УСПЕШНО ЗАВЕРШЕНА!"
    echo "Ваше приложение готово: dist/SimpleMessenger.app"
else
    echo "ОШИБКА: Приложение не было собрано. Проверьте логи выше. "
    exit 1
fi