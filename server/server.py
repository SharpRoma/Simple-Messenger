import asyncio
import json
import argparse
import db

clients = {}  # {username: writer}


async def send_to_user(username, data):
    """Отправляет JSON-сообщение конкретному пользователю, если он онлайн"""
    if username in clients:
        writer = clients[username]
        try:
            writer.write(json.dumps(data).encode() + b'\n')
            await writer.drain()
        except Exception:
            pass


async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"[Подключение] {addr}")
    username = None

    try:
        # 1. АВТОРИЗАЦИЯ (Ожидаем первый пакет)
        auth_line = await reader.readline()
        if not auth_line:
            return

        auth_data = json.loads(auth_line.decode().strip())
        username = auth_data.get('username')
        password = auth_data.get('password')

        if not db.verify_user(username, password):
            writer.write(json.dumps({"status": "error", "msg": "Неверный логин или пароль"}).encode() + b'\n')
            await writer.drain()
            print(f"[Отказ] {addr} пытался войти как {username}")
            return

        # Успешный вход
        writer.write(json.dumps({"status": "ok"}).encode() + b'\n')
        await writer.drain()

        # Выкидываем старую сессию, если юзер зашел с другого устройства
        if username in clients:
            clients[username].close()
        clients[username] = writer
        print(f"[{username}] вошел в сеть.")

        # 2. ОСНОВНОЙ ЦИКЛ ОБРАБОТКИ ДЕЙСТВИЙ
        while True:
            line = await reader.readline()
            if not line:
                break

            data = json.loads(line.decode().strip())
            action = data.get("action")

            # --- ОТПРАВКА СООБЩЕНИЯ ---
            if action == "send_msg":
                chat_id = data.get("chat_id")
                text = data.get("text")

                # Проверяем, есть ли у юзера доступ к этому чату
                if db.check_user_in_chat(chat_id, username) and text:
                    msg_obj = db.save_message(chat_id, username, text)
                    members = db.get_chat_members(chat_id)

                    notify_msg = {
                        "action": "new_msg",
                        "chat_id": chat_id,
                        "message": msg_obj
                    }
                    # Рассылаем только участникам чата, которые сейчас онлайн
                    for member in members:
                        await send_to_user(member, notify_msg)

            # --- ЗАПРОС ИСТОРИИ ---
            elif action == "get_history":
                chat_id = data.get("chat_id")
                limit = data.get("limit", 50)
                offset = data.get("offset", 0)

                if db.check_user_in_chat(chat_id, username):
                    messages = db.get_history(chat_id, limit, offset)
                    await send_to_user(username, {
                        "action": "history",
                        "chat_id": chat_id,
                        "messages": messages
                    })

            # --- ЗАПРОС СПИСКА ЧАТОВ ---
            elif action == "get_chats":
                chats = db.get_user_chats(username)
                await send_to_user(username, {
                    "action": "chat_list",
                    "chats": chats
                })

            # --- СОЗДАНИЕ ЛИЧКИ (ДИАЛОГА) ---
            elif action == "create_dialog":
                target = data.get("target")
                if not db.user_exists(target):
                    await send_to_user(username, {"action": "error", "msg": f"Пользователь {target} не найден."})
                    continue

                chat_id = db.get_or_create_dialog(username, target)
                await send_to_user(username, {
                    "action": "dialog_created",
                    "target": target,
                    "chat_id": chat_id
                })

    except json.JSONDecodeError:
        pass  # Игнорируем битые пакеты
    except ConnectionResetError:
        pass
    except Exception as e:
        print(f"Ошибка клиента {username}: {e}")
    finally:
        if username and clients.get(username) == writer:
            del clients[username]
            print(f"[{username}] отключился.")
        writer.close()


async def start_server(host, port):
    db.init_db()
    server = await asyncio.start_server(handle_client, host, port)
    print(f"🚀 Сервер запущен на {host}:{port}")
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Messenger Server")
    parser.add_argument('--add-user', nargs=2, metavar=('LOGIN', 'PASS'), help="Создать учетку")
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