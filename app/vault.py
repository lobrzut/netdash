import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.secret_key.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValueError("Nie udało się odszyfrować wpisu")


def mask_secret(value: str) -> str:
    if len(value) <= 4:
        return "•" * len(value)
    return "•" * 12 + value[-4:]
