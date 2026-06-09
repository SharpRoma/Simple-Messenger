import sqlite3
import bcrypt
import time
import os

# Жесткая привязка к папке data/ рядом с этим скриптом
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, 'messenger.db')

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, type TEXT)')
        conn.execute('''CREATE TABLE IF NOT EXISTS chat_members (
            chat_id INTEGER, username TEXT, FOREIGN KEY(chat_id) REFERENCES chats(id), 
            FOREIGN KEY(username) REFERENCES users(username), UNIQUE(chat_id, username))''')

        # ДОБАВЛЕНЫ file_name и file_path
        conn.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, sender TEXT, text TEXT, 
            file_name TEXT, file_path TEXT, timestamp INTEGER,
            FOREIGN KEY(chat_id) REFERENCES chats(id), FOREIGN KEY(sender) REFERENCES users(username))''')

        conn.execute("INSERT OR IGNORE INTO chats (id, name, type) VALUES (1, 'Общий чат', 'global')")


def add_user(username, password) -> bool:
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute('INSERT INTO users VALUES (?, ?)', (username, hashed_password))
            cur.execute('INSERT INTO chat_members (chat_id, username) VALUES (1, ?)', (username,))
            cur.execute("INSERT INTO chats (name, type) VALUES ('Избранное', 'saved')")
            saved_chat_id = cur.lastrowid
            cur.execute('INSERT INTO chat_members (chat_id, username) VALUES (?, ?)', (saved_chat_id, username))
            return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username, password) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT password FROM users WHERE username=?', (username,))
        row = cur.fetchone()
        if row: return bcrypt.checkpw(password.encode('utf-8'), row[0].encode('utf-8'))
        return False


def get_or_create_dialog(user1, user2):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('''SELECT chat_id FROM chats c JOIN chat_members m ON c.id = m.chat_id
            WHERE c.type = 'dialog' AND m.username IN (?, ?) GROUP BY chat_id HAVING COUNT(DISTINCT m.username) = 2''',
                    (user1, user2))
        row = cur.fetchone()
        if row: return row[0]
        cur.execute("INSERT INTO chats (name, type) VALUES (?, 'dialog')", (f"{user1}_{user2}",))
        chat_id = cur.lastrowid
        cur.execute("INSERT INTO chat_members (chat_id, username) VALUES (?, ?)", (chat_id, user1))
        cur.execute("INSERT INTO chat_members (chat_id, username) VALUES (?, ?)", (chat_id, user2))
        return chat_id


def save_message(chat_id, sender, text="", file_name=None, file_path=None):
    timestamp = int(time.time())
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO messages (chat_id, sender, text, file_name, file_path, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
            (chat_id, sender, text, file_name, file_path, timestamp))
        msg_id = cur.lastrowid
        return {"id": msg_id, "sender": sender, "text": text, "file_name": file_name, "timestamp": timestamp}


def delete_message(msg_id, username):
    """Удаляет сообщение из БД. Если к нему прикреплен файл - возвращает путь к нему для удаления с диска"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT sender, file_path FROM messages WHERE id=?', (msg_id,))
        row = cur.fetchone()
        if not row or row[0] != username:
            return False
        cur.execute('DELETE FROM messages WHERE id=?', (msg_id,))
        return {"file_path": row[1]}


def get_history(chat_id, limit=50, offset=0):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT id, sender, text, file_name, timestamp FROM messages WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?',
            (chat_id, limit, offset))
        rows = cur.fetchall()
        return [{"id": r[0], "sender": r[1], "text": r[2], "file_name": r[3], "timestamp": r[4]} for r in
                reversed(rows)]


def get_message_file(msg_id, username):
    """Проверяет права юзера и возвращает путь к файлу для скачивания"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('''SELECT m.file_path, m.file_name FROM messages m JOIN chat_members c ON m.chat_id = c.chat_id
                       WHERE m.id=? AND c.username=?''', (msg_id, username))
        row = cur.fetchone()
        if row: return row[0], row[1]
        return None, None


def check_user_in_chat(chat_id, username):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT 1 FROM chat_members WHERE chat_id=? AND username=?', (chat_id, username))
        return bool(cur.fetchone())


def get_chat_members(chat_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT username FROM chat_members WHERE chat_id=?', (chat_id,))
        return [row[0] for row in cur.fetchall()]


def get_user_chats(username):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            '''SELECT c.id, c.name, c.type FROM chats c JOIN chat_members m ON c.id = m.chat_id WHERE m.username = ?''',
            (username,))
        return [{"id": r[0], "name": r[1], "type": r[2]} for r in cur.fetchall()]


def user_exists(username):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT 1 FROM users WHERE username=?', (username,))
        return bool(cur.fetchone())