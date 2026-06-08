"""
DATA-AI 数据加密模块

提供敏感数据的加密存储和安全传输能力。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from pathlib import Path

from .logging import get_logger

logger = get_logger(__name__)


class EncryptionError(Exception):
    """加密相关错误"""

    pass


@dataclass
class EncryptionConfig:
    """加密配置"""

    algorithm: str = "AES-256-GCM"
    key_derivation: str = "PBKDF2"
    iterations: int = 100000
    salt_length: int = 16
    nonce_length: int = 12


class DataEncryptor:
    """
    数据加密器

    支持：
    - AES-256-GCM 加密（需要 cryptography 库）
    - Fernet 加密（需要 cryptography 库）
    - 简单 XOR 加密（无需额外依赖，仅用于非敏感场景）
    - 密码哈希（PBKDF2 / bcrypt）
    - API 密钥掩码
    """

    def __init__(self, config: EncryptionConfig | None = None):
        self._config = config or EncryptionConfig()
        self._has_crypto = self._check_crypto()

    @staticmethod
    def _check_crypto() -> bool:
        """检查 cryptography 库是否可用"""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            return True
        except ImportError:
            return False

    def encrypt(self, plaintext: str, password: str) -> str:
        """
        加密文本

        Args:
            plaintext: 明文
            password: 加密密码

        Returns:
            Base64 编码的加密数据
        """
        if self._has_crypto:
            return self._encrypt_aes_gcm(plaintext, password)
        else:
            return self._encrypt_simple(plaintext, password)

    def decrypt(self, ciphertext: str, password: str) -> str:
        """
        解密文本

        Args:
            ciphertext: Base64 编码的加密数据
            password: 加密密码

        Returns:
            明文
        """
        if self._has_crypto:
            return self._decrypt_aes_gcm(ciphertext, password)
        else:
            return self._decrypt_simple(ciphertext, password)

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """从密码派生密钥"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self._config.iterations,
        )
        return kdf.derive(password.encode())

    def _encrypt_aes_gcm(self, plaintext: str, password: str) -> str:
        """AES-256-GCM 加密"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        salt = secrets.token_bytes(self._config.salt_length)
        nonce = secrets.token_bytes(self._config.nonce_length)
        key = self._derive_key(password, salt)

        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

        # 格式: salt + nonce + ciphertext
        payload = salt + nonce + ciphertext
        return base64.b64encode(payload).decode()

    def _decrypt_aes_gcm(self, ciphertext: str, password: str) -> str:
        """AES-256-GCM 解密"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        try:
            payload = base64.b64decode(ciphertext)
        except Exception:
            raise EncryptionError("无效的加密数据格式")

        salt = payload[: self._config.salt_length]
        nonce = payload[self._config.salt_length : self._config.salt_length + self._config.nonce_length]
        ct = payload[self._config.salt_length + self._config.nonce_length :]

        key = self._derive_key(password, salt)
        aesgcm = AESGCM(key)

        try:
            plaintext = aesgcm.decrypt(nonce, ct, None)
            return plaintext.decode()
        except Exception:
            raise EncryptionError("解密失败，密码可能不正确")

    def _encrypt_simple(self, plaintext: str, password: str) -> str:
        """简单 XOR 加密（备用方案）"""
        password_hash = hashlib.sha256(password.encode()).digest()
        plaintext_bytes = plaintext.encode()

        # 生成随机 salt
        salt = secrets.token_bytes(16)

        # XOR 加密
        encrypted = bytearray()
        for i, byte in enumerate(plaintext_bytes):
            key_byte = password_hash[i % len(password_hash)]
            encrypted.append(byte ^ key_byte ^ salt[i % len(salt)])

        payload = salt + bytes(encrypted)
        return base64.b64encode(payload).decode()

    def _decrypt_simple(self, ciphertext: str, password: str) -> str:
        """简单 XOR 解密"""
        try:
            payload = base64.b64decode(ciphertext)
        except Exception:
            raise EncryptionError("无效的加密数据格式")

        salt = payload[:16]
        encrypted = payload[16:]
        password_hash = hashlib.sha256(password.encode()).digest()

        decrypted = bytearray()
        for i, byte in enumerate(encrypted):
            key_byte = password_hash[i % len(password_hash)]
            decrypted.append(byte ^ key_byte ^ salt[i % len(salt)])

        try:
            return decrypted.decode()
        except Exception:
            raise EncryptionError("解密失败")

    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        """
        密码哈希（PBKDF2）

        Returns:
            (hash_hex, salt_hex)
        """
        if salt is None:
            salt = secrets.token_hex(16)

        hash_val = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            100000,
        )

        return hash_val.hex(), salt

    @staticmethod
    def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
        """验证密码"""
        hash_val = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt_hex.encode(),
            100000,
        )
        return hmac.compare_digest(hash_val.hex(), hash_hex)

    @staticmethod
    def mask_api_key(api_key: str, visible_chars: int = 4) -> str:
        """
        掩码 API 密钥

        Examples:
            mask_api_key("sk-abc123def456") -> "sk-a********************"
        """
        if not api_key:
            return ""

        if len(api_key) <= visible_chars * 2:
            return "*" * len(api_key)

        prefix = api_key[:visible_chars]
        masked = "*" * (len(api_key) - visible_chars)
        return f"{prefix}{masked}"

    @staticmethod
    def generate_api_key(prefix: str = "dai") -> str:
        """生成随机 API 密钥"""
        token = secrets.token_urlsafe(32)
        return f"{prefix}_{token}"

    def encrypt_file(self, file_path: str, password: str, output_path: str | None = None) -> str:
        """加密文件"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        encrypted = self.encrypt(content, password)

        out = output_path or str(path) + ".encrypted"
        with open(out, "w", encoding="utf-8") as f:
            f.write(encrypted)

        return out

    def decrypt_file(self, file_path: str, password: str, output_path: str | None = None) -> str:
        """解密文件"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(path, encoding="utf-8") as f:
            encrypted = f.read()

        content = self.decrypt(encrypted, password)

        out = output_path or str(path).replace(".encrypted", ".decrypted")
        with open(out, "w", encoding="utf-8") as f:
            f.write(content)

        return out


# 全局加密器实例
_global_encryptor: DataEncryptor | None = None


def get_encryptor() -> DataEncryptor:
    """获取全局加密器"""
    global _global_encryptor
    if _global_encryptor is None:
        _global_encryptor = DataEncryptor()
    return _global_encryptor
