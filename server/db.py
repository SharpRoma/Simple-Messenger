import sqlite3
import bcrypt

DB_FILE = 'messenger.db'


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT
            )
        ''')


def add_user(username, password):
    # bcrypt.hashpw принимает и возвращает байты, поэтому переводим в строку для SQLite
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute('INSERT INTO users VALUES (?, ?)', (username, hashed_password))
            print(f"✅ Пользователь '{username}' успешно создан!")
    except sqlite3.IntegrityError:
        print(f"❌ Ошибка: Пользователь '{username}' уже существует.")


def verify_user(username, password) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute('SELECT password FROM users WHERE username=?', (username,))
        row = cur.fetchone()

        if row:
            stored_hash = row[0].encode('utf-8')  # Достаем из БД и переводим обратно в байты
            # bcrypt сам достанет соль из stored_hash и сверит пароли
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash)
        return False