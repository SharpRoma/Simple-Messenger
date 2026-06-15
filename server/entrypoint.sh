#!/bin/bash

mkdir -p /app/data

# Генерируем 10-летние ключи, если их нет
if [ ! -f "/app/data/cert.pem" ]; then
    echo "SSL-сертификаты не найдены. Генерирую новые..."
    openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
        -keyout /app/data/key.pem -out /app/data/cert.pem \
        -subj "/C=RU/O=SimpleMessenger/CN=127.0.0.1" > /dev/null 2>&1
    echo "Сертификаты успешно созданы!"
fi

echo "Запуск FastAPI сервера с SSL-шифрованием..."
# Запускаем Uvicorn, передавая ему сгенерированные ключи!
exec uvicorn main:app --host 0.0.0.0 --port 8888 --ssl-keyfile /app/data/key.pem --ssl-certfile /app/data/cert.pem