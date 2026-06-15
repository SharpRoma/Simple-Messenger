FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/SharpRoma/Simple-Messenger"

# Устанавливаем openssl для генерации сертификатов
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8888

CMD ["./entrypoint.sh"]