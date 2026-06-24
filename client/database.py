import sqlite3
from pathlib import Path

class ClientDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL
                )
            """)
            try:
                conn.execute("ALTER TABLE chats ADD COLUMN symmetric_key TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    sender TEXT NOT NULL,
                    text TEXT,
                    file_name TEXT,
                    local_path TEXT,
                    timestamp INTEGER NOT NULL,
                    updated_at INTEGER,
                    is_read INTEGER DEFAULT 0,
                    FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                )
            """)
            try:
                conn.execute("ALTER TABLE messages ADD COLUMN local_path TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            conn.commit()

    def save_chats(self, chats: list[dict]):
        with self._get_conn() as conn:
            for chat in chats:
                symmetric_key = chat.get("symmetric_key")
                conn.execute("""
                    INSERT INTO chats (id, name, type, symmetric_key)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        type = excluded.type,
                        symmetric_key = COALESCE(excluded.symmetric_key, chats.symmetric_key)
                """, (chat["id"], chat["name"], chat["type"], symmetric_key))
            conn.commit()

    def get_chats(self) -> list[dict]:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT id, name, type, symmetric_key FROM chats")
            return [dict(row) for row in cursor.fetchall()]

    def save_messages(self, chat_id: int, messages: list[dict]):
        with self._get_conn() as conn:
            for msg in messages:
                conn.execute("""
                    INSERT INTO messages 
                    (id, chat_id, sender, text, file_name, timestamp, updated_at, is_read) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        chat_id = excluded.chat_id,
                        sender = excluded.sender,
                        text = excluded.text,
                        file_name = excluded.file_name,
                        timestamp = excluded.timestamp,
                        updated_at = excluded.updated_at,
                        is_read = excluded.is_read
                """, (
                    msg["id"],
                    chat_id,
                    msg["sender"],
                    msg.get("text"),
                    msg.get("file_name"),
                    msg["timestamp"],
                    msg.get("updated_at"),
                    1 if msg.get("is_read") else 0
                ))
            conn.commit()

    def get_messages(self, chat_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT id, sender, text, file_name, local_path, timestamp, updated_at, is_read 
                FROM messages 
                WHERE chat_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
            """, (chat_id, limit, offset))
            rows = cursor.fetchall()
            msg_list = []
            for r in reversed(rows):
                d = dict(r)
                d["is_read"] = bool(d["is_read"])
                msg_list.append(d)
            return msg_list

    def get_chat_files(self, chat_id: int) -> list[dict]:
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT id, sender, text, file_name, local_path, timestamp, updated_at, is_read 
                FROM messages 
                WHERE chat_id = ? AND file_name IS NOT NULL
                ORDER BY timestamp DESC
            """, (chat_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_chat_links(self, chat_id: int) -> list[dict]:
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT id, sender, text, timestamp 
                FROM messages 
                WHERE chat_id = ? AND (text LIKE '%http://%' OR text LIKE '%https://%')
                ORDER BY timestamp DESC
            """, (chat_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def update_message_local_path(self, msg_id: int, local_path: str):
        with self._get_conn() as conn:
            conn.execute("UPDATE messages SET local_path = ? WHERE id = ?", (local_path, msg_id))
            conn.commit()

    def delete_message(self, msg_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
            conn.commit()

    def update_message(self, msg_id: int, text: str, file_name: str, updated_at: int, is_read: bool):
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE messages 
                SET text = ?, file_name = ?, updated_at = ?, is_read = ? 
                WHERE id = ?
            """, (text, file_name, updated_at, 1 if is_read else 0, msg_id))
            conn.commit()

    def mark_chat_as_read(self, chat_id: int, current_username: str):
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE messages 
                SET is_read = 1 
                WHERE chat_id = ? AND sender != ?
            """, (chat_id, current_username))
            conn.commit()

    def search_messages(self, chat_id: int, query: str) -> list[dict]:
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT id, sender, text, file_name, local_path, timestamp, updated_at, is_read 
                FROM messages 
                WHERE chat_id = ? AND (text LIKE ? OR file_name LIKE ?)
                ORDER BY timestamp DESC
            """, (chat_id, f"%{query}%", f"%{query}%"))
            rows = cursor.fetchall()
            msg_list = []
            for r in reversed(rows):
                d = dict(r)
                d["is_read"] = bool(d["is_read"])
                msg_list.append(d)
            return msg_list
