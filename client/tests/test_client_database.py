import pytest
from pathlib import Path
from database import ClientDatabase

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_client_cache.sqlite"
    db = ClientDatabase(db_file)
    return db

def test_save_and_get_chats(temp_db):
    chats = [
        {"id": 1, "name": "General", "type": "group"},
        {"id": 2, "name": "alice_bob", "type": "dialog"}
    ]
    temp_db.save_chats(chats)
    
    loaded_chats = temp_db.get_chats()
    assert len(loaded_chats) == 2
    chat_dict = {c["id"]: c for c in loaded_chats}
    assert chat_dict[1]["name"] == "General"
    assert chat_dict[1]["type"] == "group"
    assert chat_dict[2]["name"] == "alice_bob"
    assert chat_dict[2]["type"] == "dialog"

def test_save_and_get_messages(temp_db):
    temp_db.save_chats([{"id": 1, "name": "General", "type": "group"}])
    
    messages = [
        {
            "id": 10,
            "sender": "alice",
            "text": "Hello world",
            "file_name": None,
            "timestamp": 1000,
            "updated_at": None,
            "is_read": False
        },
        {
            "id": 11,
            "sender": "bob",
            "text": "Hi alice",
            "file_name": "photo.png",
            "timestamp": 1001,
            "updated_at": 1002,
            "is_read": True
        }
    ]
    
    temp_db.save_messages(1, messages)
    
    loaded_msgs = temp_db.get_messages(1)
    assert len(loaded_msgs) == 2
    
    assert loaded_msgs[0]["id"] == 10
    assert loaded_msgs[0]["sender"] == "alice"
    assert loaded_msgs[0]["text"] == "Hello world"
    assert loaded_msgs[0]["file_name"] is None
    assert loaded_msgs[0]["timestamp"] == 1000
    assert loaded_msgs[0]["updated_at"] is None
    assert loaded_msgs[0]["is_read"] is False
    
    assert loaded_msgs[1]["id"] == 11
    assert loaded_msgs[1]["sender"] == "bob"
    assert loaded_msgs[1]["text"] == "Hi alice"
    assert loaded_msgs[1]["file_name"] == "photo.png"
    assert loaded_msgs[1]["timestamp"] == 1001
    assert loaded_msgs[1]["updated_at"] == 1002
    assert loaded_msgs[1]["is_read"] is True

def test_delete_message(temp_db):
    temp_db.save_chats([{"id": 1, "name": "General", "type": "group"}])
    messages = [
        {"id": 10, "sender": "alice", "text": "Hello", "timestamp": 1000}
    ]
    temp_db.save_messages(1, messages)
    
    assert len(temp_db.get_messages(1)) == 1
    temp_db.delete_message(10)
    assert len(temp_db.get_messages(1)) == 0

def test_update_message(temp_db):
    temp_db.save_chats([{"id": 1, "name": "General", "type": "group"}])
    messages = [
        {"id": 10, "sender": "alice", "text": "Hello", "timestamp": 1000, "is_read": False}
    ]
    temp_db.save_messages(1, messages)
    
    temp_db.update_message(10, "Hello (edited)", "file.txt", 1050, True)
    
    loaded = temp_db.get_messages(1)
    assert len(loaded) == 1
    msg = loaded[0]
    assert msg["text"] == "Hello (edited)"
    assert msg["file_name"] == "file.txt"
    assert msg["updated_at"] == 1050
    assert msg["is_read"] is True

def test_mark_chat_as_read(temp_db):
    temp_db.save_chats([{"id": 1, "name": "General", "type": "group"}])
    messages = [
        {"id": 10, "sender": "alice", "text": "Hello", "timestamp": 1000, "is_read": False},
        {"id": 11, "sender": "bob", "text": "Hi", "timestamp": 1001, "is_read": False}
    ]
    temp_db.save_messages(1, messages)
    
    temp_db.mark_chat_as_read(1, "bob")
    
    loaded = temp_db.get_messages(1)
    msg_alice = next(m for m in loaded if m["sender"] == "alice")
    msg_bob = next(m for m in loaded if m["sender"] == "bob")
    
    assert msg_alice["is_read"] is True
    assert msg_bob["is_read"] is False

def test_get_chat_files(temp_db):
    temp_db.save_chats([{"id": 1, "name": "General", "type": "group"}])
    messages = [
        {"id": 10, "sender": "alice", "text": "Hello", "timestamp": 1000, "file_name": None},
        {"id": 11, "sender": "bob", "text": "Photo here", "timestamp": 1001, "file_name": "photo.png"},
        {"id": 12, "sender": "alice", "text": "Doc here", "timestamp": 1002, "file_name": "doc.pdf"}
    ]
    temp_db.save_messages(1, messages)
    
    files = temp_db.get_chat_files(1)
    assert len(files) == 2
    assert files[0]["id"] == 12
    assert files[0]["file_name"] == "doc.pdf"
    assert files[1]["id"] == 11
    assert files[1]["file_name"] == "photo.png"

def test_symmetric_key_saving_and_migration(temp_db):
    # Тест ON CONFLICT и COALESCE
    chats = [{"id": 42, "name": "secret_chat", "type": "secret", "symmetric_key": "AesKeyBase64String"}]
    temp_db.save_chats(chats)

    loaded = temp_db.get_chats()
    assert loaded[0]["symmetric_key"] == "AesKeyBase64String"

    # Теперь присылаем чат из списка без symmetric_key (как придет с сервера перед расшифрованием)
    chats_update = [{"id": 42, "name": "secret_chat", "type": "secret"}]
    temp_db.save_chats(chats_update)

    loaded_again = temp_db.get_chats()
    # Проверяем, что ключ сохранился и не затерся NULL-ом
    assert loaded_again[0]["symmetric_key"] == "AesKeyBase64String"

def test_search_messages_local(temp_db):
    temp_db.save_chats([{"id": 1, "name": "secret", "type": "secret"}])
    messages = [
        {"id": 10, "sender": "alice", "text": "secret info about project", "timestamp": 1000},
        {"id": 11, "sender": "bob", "text": "nothing sensitive here", "timestamp": 1001, "file_name": "important_presentation.pdf"},
        {"id": 12, "sender": "alice", "text": "unrelated", "timestamp": 1002}
    ]
    temp_db.save_messages(1, messages)

    # Ищем по слову "project"
    res1 = temp_db.search_messages(1, "project")
    assert len(res1) == 1
    assert res1[0]["id"] == 10

    # Ищем по имени файла "presentation"
    res2 = temp_db.search_messages(1, "presentation")
    assert len(res2) == 1
    assert res2[0]["id"] == 11

