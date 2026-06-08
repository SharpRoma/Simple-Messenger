import asyncio
import json
import argparse
import db

clients = {}  # Словарь {username: asyncio.StreamWriter}


async def broadcast(message_dict):
    """Рассылает сообщение всем подключенным клиентам"""
    line = json.dumps(message_dict).encode() + b'\n'
    for user, writer in clients.items():
        try:
            writer.write(line)
            await writer.drain()
        except Exception:
            pass


async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"[Подключение] {addr}")

    # 1. Ожидаем пакет авторизации
    auth_line = await reader.readline()
    if not auth_line:
        writer.close()
        return

    try:
        auth_data = json.loads(auth_line.decode().strip())
        username = auth_data.get('username')
        password = auth_data.get('password')
    except json.JSONDecodeError:
        writer.close()
        return

    # 2. Проверяем в БД
    if not db.verify_user(username, password):
        writer.write(json.dumps({"status": "error", "msg": "Неверный логин или пароль"}).encode() + b'\n')
        await writer.drain()
        writer.close()
        print(f"[Отказ в доступе] {addr} пытался войти как {username}")
        return

    # 3. Успешный вход
    writer.write(json.dumps({"status": "ok"}).encode() + b'\n')
    await writer.drain()

    # Если пользователь уже онлайн с другого устройства — отключаем старое
    if username in clients:
        clients[username].close()

    clients[username] = writer
    print(f"[Авторизация] {username} вошел в чат.")
    await broadcast({"sender": "SERVER", "msg": f"Пользователь {username} зашел в чат!"})

    # 4. Основной цикл общения
    try:
        while True:
            line = await reader.readline()
            if not line:
                break  # Клиент отключился

            data = json.loads(line.decode().strip())
            msg_text = data.get('msg')

            if msg_text:
                await broadcast({"sender": username, "msg": msg_text})
                print(f"[{username}]: {msg_text}")
    except ConnectionResetError:
        pass
    finally:
        if clients.get(username) == writer:
            del clients[username]
        writer.close()
        await broadcast({"sender": "SERVER", "msg": f"{username} покинул чат."})
        print(f"[Отключение] {username} вышел.")


async def start_server(host, port):
    db.init_db()
    server = await asyncio.start_server(handle_client, host, port)
    print(f"🚀 Сервер запущен на {host}:{port}")
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Simple Messenger Server")
    parser.add_argument('--add-user', nargs=2, metavar=('LOGIN', 'PASS'),
                        help="Создать учетку (Пример: --add-user admin 1234)")
    parser.add_argument('--run', action='store_true', help="Запустить сервер")
    parser.add_argument('--port', type=int, default=8888, help="Порт (по умолчанию 8888)")

    args = parser.parse_args()

    if args.add_user:
        db.init_db()
        db.add_user(args.add_user[0], args.add_user[1])
    elif args.run:
        asyncio.run(start_server('0.0.0.0', args.port))
    else:
        parser.print_help()