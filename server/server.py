import asyncio
import json
import argparse
import db
import base64
import os
import uuid
import ssl  # <--- БИБЛИОТЕКА ДЛЯ ШИФРОВАНИЯ
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)

load_dotenv(os.path.join(BASE_DIR, ".env"))
SERVER_SECRET = os.environ.get("SERVER_SECRET")

if not SERVER_SECRET:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Переменная SERVER_SECRET не найдена в файле .env!")

clients = {}


async def send_to_user(username, data):
    if username in clients:
        line = json.dumps(data).encode() + b'\n'
        for writer in list(clients[username]):
            try:
                writer.write(line)
                await writer.drain()
            except:
                pass


async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"[Подключение] {addr} (Зашифровано: {writer.get_extra_info('sslcontext') is not None})")
    username = None

    try:
        auth_line = await reader.readline()
        if not auth_line: return

        auth_data = json.loads(auth_line.decode().strip())
        mode = auth_data.get('mode', 'login')
        username = auth_data.get('username')
        password = auth_data.get('password')

        if mode == "register":
            secret = auth_data.get('secret')
            if secret != SERVER_SECRET:
                writer.write(json.dumps({"status": "error", "msg": "Неверный секретный код сервера!"}).encode() + b'\n')
                return
            if not db.add_user(username, password):
                writer.write(json.dumps({"status": "error", "msg": "Пользователь уже существует"}).encode() + b'\n')
                return
            print(f"[Регистрация] Создан новый юзер: {username}")

        if not db.verify_user(username, password):
            writer.write(json.dumps({"status": "error", "msg": "Неверный логин или пароль"}).encode() + b'\n')
            return

        writer.write(json.dumps({"status": "ok"}).encode() + b'\n')
        await writer.drain()

        if username not in clients: clients[username] = set()
        clients[username].add(writer)
        print(f"[{username}] вошел в сеть.")

        while True:
            line = await reader.readline()
            if not line: break

            data = json.loads(line.decode().strip())
            action = data.get("action")

            if action == "send_msg":
                chat_id, text = data.get("chat_id"), data.get("text")
                if db.check_user_in_chat(chat_id, username) and text:
                    msg_obj = db.save_message(chat_id, username, text=text)
                    for member in db.get_chat_members(chat_id):
                        await send_to_user(member, {"action": "new_msg", "chat_id": chat_id, "message": msg_obj})

            elif action == "send_file":
                chat_id, filename, b64_data = data.get("chat_id"), data.get("filename"), data.get("data")
                if db.check_user_in_chat(chat_id, username) and filename and b64_data:
                    ext = os.path.splitext(filename)[1]
                    unique_name = f"{uuid.uuid4()}{ext}"
                    file_path = os.path.join(UPLOAD_DIR, unique_name)

                    with open(file_path, "wb") as f:
                        f.write(base64.b64decode(b64_data))

                    msg_obj = db.save_message(chat_id, username, file_name=filename, file_path=file_path)
                    for member in db.get_chat_members(chat_id):
                        await send_to_user(member, {"action": "new_msg", "chat_id": chat_id, "message": msg_obj})

            elif action == "req_file":
                msg_id = data.get("msg_id")
                file_path, file_name = db.get_message_file(msg_id, username)
                if file_path and os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        b64_data = base64.b64encode(f.read()).decode('utf-8')
                    writer.write(json.dumps({"action": "res_file", "msg_id": msg_id, "filename": file_name,
                                             "data": b64_data}).encode() + b'\n')
                    await writer.drain()

            elif action == "delete_msg":
                msg_id, chat_id = data.get("msg_id"), data.get("chat_id")
                del_result = db.delete_message(msg_id, username)
                if del_result is not False:
                    file_path = del_result.get("file_path")
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)

                    for member in db.get_chat_members(chat_id):
                        await send_to_user(member, {"action": "msg_deleted", "chat_id": chat_id, "msg_id": msg_id})

            elif action == "get_history":
                chat_id, limit, offset = data.get("chat_id"), data.get("limit", 50), data.get("offset", 0)
                if db.check_user_in_chat(chat_id, username):
                    writer.write(json.dumps({"action": "history", "chat_id": chat_id,
                                             "messages": db.get_history(chat_id, limit, offset)}).encode() + b'\n')
                    await writer.drain()

            elif action == "get_chats":
                writer.write(json.dumps({"action": "chat_list", "chats": db.get_user_chats(username)}).encode() + b'\n')
                await writer.drain()

            elif action == "create_dialog":
                target = data.get("target")
                if not db.user_exists(target):
                    writer.write(
                        json.dumps({"action": "error", "msg": f"Пользователь {target} не найден."}).encode() + b'\n')
                    await writer.drain()
                    continue
                chat_id = db.get_or_create_dialog(username, target)
                writer.write(
                    json.dumps({"action": "dialog_created", "target": target, "chat_id": chat_id}).encode() + b'\n')
                await writer.drain()

    except Exception:
        pass
    finally:
        if username and username in clients:
            if writer in clients[username]: clients[username].remove(writer)
            if not clients[username]: del clients[username]
        writer.close()


async def start_server(host, port):
    db.init_db()

    # --- НАСТРОЙКА SSL КОНТЕКСТА ---
    cert_path = os.path.join(DATA_DIR, "cert.pem")
    key_path = os.path.join(DATA_DIR, "key.pem")

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print("ОШИБКА: Сертификаты SSL не найдены! Выполните команду openssl.")
        return

    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)

    # Передаем ssl_context в сокет!
    server = await asyncio.start_server(handle_client, host, port, ssl=ssl_context, limit=1024 * 1024 * 50)
    print(f"SSL/TLS сервер запущен на {host}:{port}")
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Messenger Server")
    parser.add_argument('--run', action='store_true', help="Запустить сервер")
    parser.add_argument('--port', type=int, default=8888, help="Порт")
    parser.add_argument('--secret', type=str, default=None, help="Код для регистрации")
    args = parser.parse_args()

    if args.run:
        asyncio.run(start_server('0.0.0.0', args.port))
    else:
        parser.print_help()