import pytest
import os
import base64
from pathlib import Path
from unittest.mock import patch
from system.crypto import CryptoManager


@pytest.fixture
def temp_keys_dir(tmp_path):
    return tmp_path / "keys"


@pytest.fixture(autouse=True)
def mock_keyring():
    fake_keyring = {}
    def mock_get(service, username):
        return fake_keyring.get((service, username))
    def mock_set(service, username, password):
        fake_keyring[(service, username)] = password
    
    with patch("keyring.get_password", side_effect=mock_get), \
         patch("keyring.set_password", side_effect=mock_set):
        yield fake_keyring


def test_keys_generation_and_loading(temp_keys_dir):
    mgr = CryptoManager(temp_keys_dir, "test_user")
    assert not mgr.priv_key_path.exists()
    assert not mgr.pub_key_path.exists()

    mgr.init_keys()
    assert mgr.priv_key_path.exists()
    assert mgr.pub_key_path.exists()
    
    pub_key_pem = mgr.get_public_key_pem()
    assert "BEGIN PUBLIC KEY" in pub_key_pem

    # Пересоздаем менеджер и проверяем загрузку существующих ключей
    mgr_loaded = CryptoManager(temp_keys_dir, "test_user")
    mgr_loaded.init_keys()
    assert mgr_loaded.get_public_key_pem() == pub_key_pem


def test_rsa_encryption_decryption(temp_keys_dir):
    mgr = CryptoManager(temp_keys_dir, "test_user")
    mgr.init_keys()

    secret_data = b"My top secret session key 123"
    
    pub_key_pem = mgr.get_public_key_pem()
    encrypted_base64 = CryptoManager.encrypt_rsa_with_pubkey(pub_key_pem, secret_data)
    assert isinstance(encrypted_base64, str)
    assert len(encrypted_base64) > 0

    decrypted_bytes = mgr.decrypt_rsa(encrypted_base64)
    assert decrypted_bytes == secret_data


def test_aes_encryption_decryption():
    aes_key = os.urandom(32)
    plaintext = "Hello, this is a secret E2EE message! Привет мир!"

    ciphertext_base64 = CryptoManager.encrypt_aes(aes_key, plaintext)
    assert isinstance(ciphertext_base64, str)
    assert len(ciphertext_base64) > 0

    decrypted_text = CryptoManager.decrypt_aes(aes_key, ciphertext_base64)
    assert decrypted_text == plaintext


def test_unencrypted_key_migration(temp_keys_dir):
    # 1. Генерируем обычную пару ключей и вручную сохраняем приватный ключ без шифрования (старый формат)
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    temp_keys_dir.mkdir(parents=True, exist_ok=True)
    
    # Сохраняем незашифрованный приватный ключ
    pem_unencrypted = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(temp_keys_dir / "private_key.pem", "wb") as f:
        f.write(pem_unencrypted)

    # Сохраняем публичный ключ
    pem_pub = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with open(temp_keys_dir / "public_key.pem", "wb") as f:
        f.write(pem_pub)

    # 2. Инициализируем CryptoManager (он должен подгрузить незашифрованный ключ и автоматически зашифровать его)
    mgr = CryptoManager(temp_keys_dir, "migration_user")
    mgr.init_keys()

    # Проверяем, что ключ загрузился
    assert mgr.private_key is not None
    assert mgr.get_public_key_pem() == pem_pub.decode("utf-8")

    # 3. Проверяем, что на диске приватный ключ теперь зашифрован (load с password=None выбросит ошибку)
    with open(temp_keys_dir / "private_key.pem", "rb") as f:
        updated_pem = f.read()

    with pytest.raises((ValueError, TypeError)):
        serialization.load_pem_private_key(updated_pem, password=None)
