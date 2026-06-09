FROM python:3.12-slim

# Устанавливаем openssl для генерации сертификатов
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код и делаем bash-скрипт исполняемым
COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8888

# Запускаем через наш умный скрипт
CMD ["./entrypoint.sh"]