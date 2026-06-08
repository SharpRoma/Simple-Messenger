import asyncio
import json
import sys


async def receive_messages(reader):
    """Слушает сервер и выводит сообщения в консоль"""
    try:
        while True:
            line = await reader.readline()
            if not line:
                print("\n[!] Соединение с сервером потеряно.")
                break

            data = json.loads(line.decode().strip())
            sender = data.get("sender", "Unknown")
            msg = data.get("msg", "")

            # \r стирает текущую строку ввода, печатает сообщение и возвращает курсор
            sys.stdout.write(f"\r[{sender}]: {msg}\n> ")
            sys.stdout.flush()
    except Exception as e:
        print(f"Ошибка чтения: {e}")


async def send_messages(writer):
    """Ждет ввод пользователя и отправляет на сервер"""
    loop = asyncio.get_running_loop()
    try:
        while True:
            # Асинхронно ждем ввода из консоли
            msg = await loop.run_in_executor(None, input, "> ")

            if msg.lower() == '/quit':
                break

            if msg.strip():
                data = {"msg": msg}
                writer.write(json.dumps(data).encode() + b'\n')
                await writer.drain()
    except Exception as e:
        print(f"Ошибка отправки: {e}")
    finally:
        writer.close()


async def main():
    print("=== Simple Messenger CLI ===")
    host = input("IP сервера (или Enter для 127.0.0.1): ").strip() or "127.0.0.1"
    port = 8888

    username = input("Логин: ")
    password = input("Пароль: ")

    try:
        reader, writer = await asyncio.open_connection(host, port)
    except Exception as e:
        print(f"❌ Не удалось подключиться к {host}:{port} - {e}")
        return

    # 1. Отправляем данные для авторизации
    auth_data = {"username": username, "password": password}
    writer.write(json.dumps(auth_data).encode() + b'\n')
    await writer.drain()

    # 2. Ждем ответ
    response_line = await reader.readline()
    response = json.loads(response_line.decode().strip())

    if response.get("status") != "ok":
        print(f"❌ Ошибка авторизации: {response.get('msg')}")
        writer.close()
        return

    print("✅ Успешный вход! Пишите сообщения (или введите /quit для выхода).\n")

    # 3. Запускаем параллельно чтение и запись
    recv_task = asyncio.create_task(receive_messages(reader))
    send_task = asyncio.create_task(send_messages(writer))

    # Если одна из задач завершилась (например, пользователь ввел /quit) — закрываем всё
    done, pending = await asyncio.wait(
        [recv_task, send_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()


if __name__ == '__main__':
    # Убираем ошибку закрытия loop'а в Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())