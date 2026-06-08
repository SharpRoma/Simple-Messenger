import sqlite3
import bcrypt
import time

DB_FILE = 'messenger.db'


def get_connection():
    """Создает подключение и включает поддержку внешних ключей"""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        # Таблица пользователей
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT
            )
        ''')
        # Таблица чатов (типы: global, dialog, saved)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                type TEXT
            )
        ''')
        # Таблица связи пользователей и чатов
        conn.execute('''
            CREATE TABLE IF NOT EXISTS chat_members (
                chat_id INTEGER,
                username TEXT,
                FOREIGN KEY(chat_id) REFERENCES chats(id),
                FOREIGN KEY(username) REFERENCES users(username),
                UNIQUE(chat_id, username)
            )
        ''')
        # Таблица сообщений
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                sender TEXT,
                text TEXT,
                timestamp INTEGER,
                FOREIGN KEY(chat_id) REFERENCES chats(id),
                FOREIGN KEY(sender) REFERENCES users(username)
            )
        ''')

        # Создаем Общий чат (если его еще нет) с жестким id=1
        conn.execute('''
            INSERT OR IGNORE INTO chats (id, name, type) 
            VALUES (1, 'Общий чат', 'global')
        ''')


def add_user(username, password):
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # 1. Создаем учетку
            cur.execute('INSERT INTO users VALUES (?, ?)', (username, hashed_password))

            # 2. Добавляем юзера в Общий чат
            cur.execute('INSERT INTO chat_members (chat_id, username) VALUES (1, ?)', (username,))

            # 3. Создаем чат "Избранное" (заметки для себя)
            cur.execute("INSERT INTO chats (name, type) VALUES ('Избранное', 'saved')")
            saved_chat_id = cur.lastrowid

            # 4. Добавляем юзера в его "Избранное"
            cur.execute('INSERT INTO chat_members (chat_id, username) VALUES (?, ?)', (saved_chat_id, username))

            print(f"✅ Пользователь '{username}' успешно создан!")
    except sqlite3.IntegrityError:
        print(f"❌ Ошибка: Пользователь '{username}' уже существует.")


def verify_user(username, password) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT password FROM users WHERE username=?', (username,))
        row = cur.fetchone()

        if row:
            stored_hash = row[0].encode('utf-8')
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash)
        return False


def get_or_create_dialog(user1, user2):
    """Ищет личный чат между двумя пользователями, если нет - создает"""
    with get_connection() as conn:
        cur = conn.cursor()
        # Ищем общие чаты типа dialog, где состоят оба юзера
        cur.execute('''
            SELECT chat_id FROM chats c
            JOIN chat_members m ON c.id = m.chat_id
            WHERE c.type = 'dialog' AND m.username IN (?, ?)
            GROUP BY chat_id
            HAVING COUNT(DISTINCT m.username) = 2
        ''', (user1, user2))

        row = cur.fetchone()
        if row:
            return row[0]  # Возвращаем ID существующего чата

        # Если чата нет - создаем
        cur.execute("INSERT INTO chats (name, type) VALUES (?, 'dialog')", (f"{user1}_{user2}",))
        chat_id = cur.lastrowid
        cur.execute("INSERT INTO chat_members (chat_id, username) VALUES (?, ?)", (chat_id, user1))
        cur.execute("INSERT INTO chat_members (chat_id, username) VALUES (?, ?)", (chat_id, user2))
        return chat_id


def save_message(chat_id, sender, text):
    """Сохраняет сообщение и возвращает его данные"""
    timestamp = int(time.time())  # Unix-время
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO messages (chat_id, sender, text, timestamp) 
            VALUES (?, ?, ?, ?)
        ''', (chat_id, sender, text, timestamp))
        return {"sender": sender, "text": text, "timestamp": timestamp}


def get_history(chat_id, limit=50, offset=0):
    """Получает историю сообщений с пагинацией"""
    with get_connection() as conn:
        cur = conn.cursor()
        # Берем сортировку DESC, чтобы получить самые новые
        cur.execute('''
            SELECT sender, text, timestamp 
            FROM messages 
            WHERE chat_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
        ''', (chat_id, limit, offset))

        rows = cur.fetchall()

        # Переворачиваем список обратно (чтобы старые шли перед новыми для удобства чтения)
        messages = [{"sender": r[0], "text": r[1], "timestamp": r[2]} for r in reversed(rows)]
        return messages


def check_user_in_chat(chat_id, username):
    """Проверка прав доступа (состоит ли юзер в чате)"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT 1 FROM chat_members WHERE chat_id=? AND username=?', (chat_id, username))
        return bool(cur.fetchone())

def get_chat_members(chat_id):
    """Возвращает список логинов всех участников чата"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT username FROM chat_members WHERE chat_id=?', (chat_id,))
        return [row[0] for row in cur.fetchall()]

def get_user_chats(username):
    """Возвращает список всех чатов, в которых состоит пользователь"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT c.id, c.name, c.type 
            FROM chats c
            JOIN chat_members m ON c.id = m.chat_id
            WHERE m.username = ?
        ''', (username,))
        return [{"id": r[0], "name": r[1], "type": r[2]} for r in cur.fetchall()]

def user_exists(username):
    """Проверяет, существует ли пользователь в базе"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT 1 FROM users WHERE username=?', (username,))
        return bool(cur.fetchone())