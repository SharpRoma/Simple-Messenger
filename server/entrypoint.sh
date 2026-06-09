#!/bin/bash

# Создаем папку data, если её нет
mkdir -p /app/data

# Проверяем, есть ли сертификаты. Если нет - создаем!
if [ ! -f "/app/data/cert.pem" ]; then
    echo "SSL-сертификаты не найдены. Генерирую новые..."
    openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
        -keyout /app/data/key.pem -out /app/data/cert.pem \
        -subj "/C=RU/O=SimpleMessenger/CN=127.0.0.1" > /dev/null 2>&1
    echo " Сертификаты успешно созданы!"
fi

echo "Запуск сервера..."
# Передаем управление питоновскому скрипту
exec python server.py --run