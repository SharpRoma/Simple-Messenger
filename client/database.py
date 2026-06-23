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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    sender TEXT NOT NULL,
                    text TEXT,
                    file_name TEXT,
                    timestamp INTEGER NOT NULL,
                    updated_at INTEGER,
                    is_read INTEGER DEFAULT 0,
                    FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    def save_chats(self, chats: list[dict]):
        with self._get_conn() as conn:
            for chat in chats:
                conn.execute(
                    "INSERT OR REPLACE INTO chats (id, name, type) VALUES (?, ?, ?)",
                    (chat["id"], chat["name"], chat["type"])
                )
            conn.commit()

    def get_chats(self) -> list[dict]:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT id, name, type FROM chats")
            return [dict(row) for row in cursor.fetchall()]

    def save_messages(self, chat_id: int, messages: list[dict]):
        with self._get_conn() as conn:
            for msg in messages:
                conn.execute("""
                    INSERT OR REPLACE INTO messages 
                    (id, chat_id, sender, text, file_name, timestamp, updated_at, is_read) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                SELECT id, sender, text, file_name, timestamp, updated_at, is_read 
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
