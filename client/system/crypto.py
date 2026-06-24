import os
import base64
import logging
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger("messenger.crypto")

class CryptoManager:
    def __init__(self, key_dir: Path, username: str = "default"):
        self.key_dir = key_dir
        self.username = username
        self.priv_key_path = key_dir / "private_key.pem"
        self.pub_key_path = key_dir / "public_key.pem"
        self.private_key = None
        self.public_key = None

    def _get_or_create_passphrase(self) -> str:
        import keyring
        import secrets
        
        passphrase = None
        try:
            passphrase = keyring.get_password("SimpleMessenger_KeysPass", self.username)
        except Exception as e:
            logger.error(f"Failed to get key passphrase from keyring: {e}")

        if not passphrase:
            passphrase = secrets.token_hex(32)
            try:
                keyring.set_password("SimpleMessenger_KeysPass", self.username, passphrase)
            except Exception as e:
                logger.error(f"Failed to save key passphrase in keyring: {e}")
                passphrase = f"fallback_passphrase_{self.username}"
        return passphrase

    def init_keys(self):
        """Загружает или генерирует новую пару ключей RSA-2048 (приватный ключ шифруется)"""
        passphrase = self._get_or_create_passphrase()
        
        if self.priv_key_path.exists() and self.pub_key_path.exists():
            try:
                with open(self.priv_key_path, "rb") as f:
                    key_data = f.read()
                
                # Пробуем загрузить как зашифрованный
                try:
                    self.private_key = serialization.load_pem_private_key(
                        key_data, password=passphrase.encode("utf-8")
                    )
                except (ValueError, TypeError):
                    # Если ключ незашифрован (или пароль неверен), пробуем загрузить без пароля (для старых версий)
                    self.private_key = serialization.load_pem_private_key(
                        key_data, password=None
                    )
                    # Если загрузка удалась, шифруем и пересохраняем (автоматический апгрейд)
                    self._save_private_key(passphrase)

                with open(self.pub_key_path, "rb") as f:
                    self.public_key = serialization.load_pem_public_key(f.read())
                return
            except Exception as e:
                logger.error(f"Failed to load keys: {e}")

        # Генерируем новую пару
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        self.public_key = self.private_key.public_key()

        self._save_private_key(passphrase)

        # Сохраняем публичный ключ
        pem_pub = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        with open(self.pub_key_path, "wb") as f:
            f.write(pem_pub)

    def _save_private_key(self, passphrase: str):
        """Шифрует и сохраняет приватный ключ на диск"""
        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(passphrase.encode("utf-8"))
        )
        self.key_dir.mkdir(parents=True, exist_ok=True)
        with open(self.priv_key_path, "wb") as f:
            f.write(pem)

    def get_public_key_pem(self) -> str:
        """Возвращает публичный ключ в формате PEM (string)"""
        if not self.public_key:
            self.init_keys()
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode("utf-8")

    def decrypt_rsa(self, encrypted_base64: str) -> bytes:
        """Дешифрует данные, зашифрованные публичным ключом текущего пользователя"""
        if not self.private_key:
            self.init_keys()
        data = base64.b64decode(encrypted_base64)
        return self.private_key.decrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

    @staticmethod
    def encrypt_rsa_with_pubkey(pubkey_pem: str, data: bytes) -> str:
        """Шифрует данные указанным публичным RSA-ключом получателя"""
        pubkey = serialization.load_pem_public_key(pubkey_pem.encode("utf-8"))
        encrypted = pubkey.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(encrypted).decode("utf-8")

    @staticmethod
    def encrypt_aes(key: bytes, plaintext: str) -> str:
        """Шифрует строку с помощью AES-256 GCM"""
        iv = os.urandom(12)
        encryptor = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
        ).encryptor()
        
        ciphertext = encryptor.update(plaintext.encode("utf-8")) + encryptor.finalize()
        combined = iv + encryptor.tag + ciphertext
        return base64.b64encode(combined).decode("utf-8")

    @staticmethod
    def decrypt_aes(key: bytes, ciphertext_base64: str) -> str:
        """Расшифровывает строку, зашифрованную с помощью AES-256 GCM"""
        data = base64.b64decode(ciphertext_base64)
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        decryptor = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
        ).decryptor()
        
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        return decrypted.decode("utf-8")
