import asyncio
import json
import sys
from datetime import datetime

# Текущий чат, в который мы отправляем сообщения
active_chat_id = 1


def clear_line():
    """Стирает текущую строку в консоли (чтобы входящее сообщение не ломало ввод)"""
    sys.stdout.write('\r' + ' ' * 80 + '\r')
    sys.stdout.flush()


async def receive_messages(reader):
    global active_chat_id
    try:
        while True:
            line = await reader.readline()
            if not line:
                clear_line()
                print("\n[!] Соединение с сервером потеряно.")
                break

            data = json.loads(line.decode().strip())
            action = data.get("action")

            clear_line()  # Очищаем строку перед выводом данных от сервера

            if action == "new_msg":
                chat_id = data.get("chat_id")
                msg = data.get("message")
                sender = msg.get("sender")
                text = msg.get("text")
                # Конвертируем Unix Timestamp в локальное время HH:MM
                ts = datetime.fromtimestamp(msg.get("timestamp")).strftime('%H:%M')

                if chat_id == active_chat_id:
                    print(f"[{ts}] {sender}: {text}")
                else:
                    print(f"[🔔 Новое сообщение в чате ID:{chat_id}] от {sender}")

            elif action == "history":
                messages = data.get("messages", [])
                chat_id = data.get("chat_id")
                print(f"\n=== История чата {chat_id} ===")
                if not messages:
                    print("Чат пуст.")
                for msg in messages:
                    ts = datetime.fromtimestamp(msg.get("timestamp")).strftime('%H:%M')
                    print(f"[{ts}] {msg['sender']}: {msg['text']}")
                print("=========================\n")

            elif action == "chat_list":
                print("\n=== Ваши чаты ===")
                for c in data.get("chats", []):
                    # Отмечаем текущий чат звездочкой
                    marker = "*" if c['id'] == active_chat_id else " "
                    print(f"{marker} ID: {c['id']} | {c['name']} (Тип: {c['type']})")
                print("=================\n")

            elif action == "dialog_created":
                new_id = data.get("chat_id")
                target = data.get("target")
                print(f"✅ Создан/найден диалог с {target}. ID чата: {new_id}")
                print(f"👉 Введите /chat {new_id} чтобы перейти туда.")

            elif action == "error":
                print(f"❌ Ошибка: {data.get('msg')}")

            # Возвращаем курсор ввода
            sys.stdout.write("> ")
            sys.stdout.flush()

    except Exception as e:
        print(f"Ошибка чтения: {e}")


async def send_messages(writer):
    global active_chat_id
    loop = asyncio.get_running_loop()

    # Сразу после авторизации запрашиваем список чатов
    writer.write(json.dumps({"action": "get_chats"}).encode() + b'\n')
    # И историю общего чата
    writer.write(json.dumps({"action": "get_history", "chat_id": 1, "limit": 20, "offset": 0}).encode() + b'\n')
    await writer.drain()

    try:
        while True:
            # Ждем ввода пользователя
            msg = await loop.run_in_executor(None, input, "")

            if not msg.strip():
                sys.stdout.write("> ")
                sys.stdout.flush()
                continue

            # Если это команда (начинается со слеша)
            if msg.startswith('/'):
                parts = msg.split()
                cmd = parts[0].lower()

                if cmd == '/quit':
                    break
                elif cmd == '/chats':
                    writer.write(json.dumps({"action": "get_chats"}).encode() + b'\n')
                elif cmd == '/chat' and len(parts) > 1:
                    try:
                        active_chat_id = int(parts[1])
                        print(f"🔄 Переключено на чат {active_chat_id}")
                        writer.write(json.dumps(
                            {"action": "get_history", "chat_id": active_chat_id, "limit": 20}).encode() + b'\n')
                    except ValueError:
                        print("❌ ID чата должен быть числом.")
                elif cmd == '/pm' and len(parts) > 1:
                    target = parts[1]
                    writer.write(json.dumps({"action": "create_dialog", "target": target}).encode() + b'\n')
                elif cmd == '/history':
                    offset = int(parts[1]) if len(parts) > 1 else 0
                    writer.write(json.dumps({"action": "get_history", "chat_id": active_chat_id, "limit": 20,
                                             "offset": offset}).encode() + b'\n')
                else:
                    print(
                        "ℹ️ Команды:\n /chats - список чатов\n /chat <id> - войти в чат\n /pm <user> - написать в личку\n /history [смещение] - загрузить старые сообщения\n /quit - выход")
            else:
                # Если это обычный текст - отправляем его как сообщение в активный чат
                req = {"action": "send_msg", "chat_id": active_chat_id, "text": msg}
                writer.write(json.dumps(req).encode() + b'\n')

            await writer.drain()
            # Обновляем prompt после отправки
            sys.stdout.write("> ")
            sys.stdout.flush()
    except Exception as e:
        print(f"Ошибка отправки: {e}")
    finally:
        writer.close()


async def main():
    print("=== Simple Messenger CLI ===")
    host = input("IP сервера (Enter для 127.0.0.1): ").strip() or "127.0.0.1"
    port = 8888

    username = input("Логин: ")
    password = input("Пароль: ")

    try:
        reader, writer = await asyncio.open_connection(host, port)
    except Exception as e:
        print(f"❌ Не удалось подключиться: {e}")
        return

    # Авторизация
    auth_data = {"username": username, "password": password}
    writer.write(json.dumps(auth_data).encode() + b'\n')
    await writer.drain()

    response_line = await reader.readline()
    response = json.loads(response_line.decode().strip())

    if response.get("status") != "ok":
        print(f"❌ Ошибка авторизации: {response.get('msg')}")
        writer.close()
        return

    print("✅ Успешный вход! Введите /help для подсказки команд.\n")

    recv_task = asyncio.create_task(receive_messages(reader))
    send_task = asyncio.create_task(send_messages(writer))

    done, pending = await asyncio.wait(
        [recv_task, send_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())