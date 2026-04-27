import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from solders.keypair import Keypair
from db.database import get_session
from db.models import User
from config.settings import settings


def _get_cipher() -> AESGCM:
    key = bytes.fromhex(settings.ENCRYPTION_MASTER_KEY)
    return AESGCM(key)


def encrypt_private_key(private_key_bytes: bytes) -> str:
    cipher = _get_cipher()
    nonce = os.urandom(12)
    encrypted = cipher.encrypt(nonce, private_key_bytes, None)
    payload = nonce + encrypted
    return base64.b64encode(payload).decode()


def decrypt_private_key(encrypted_str: str) -> bytes:
    cipher = _get_cipher()
    payload = base64.b64decode(encrypted_str.encode())
    nonce = payload[:12]
    encrypted = payload[12:]
    return cipher.decrypt(nonce, encrypted, None)


def generate_wallet() -> tuple[str, str]:
    keypair = Keypair()
    private_key_bytes = bytes(keypair)
    wallet_address = str(keypair.pubkey())
    encrypted_key = encrypt_private_key(private_key_bytes)
    return wallet_address, encrypted_key


def get_private_key_for_user(telegram_id: int) -> str | None:
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return None
        private_key_bytes = decrypt_private_key(user.encrypted_private_key)
        keypair = Keypair.from_bytes(private_key_bytes)
        return base64.b58encode(bytes(keypair)).decode()
    finally:
        session.close()


def import_wallet_for_user(telegram_id: int, private_key_b58: str) -> str | None:
    session = get_session()
    try:
        private_key_bytes = base64.b58decode(private_key_b58.encode())
        keypair = Keypair.from_bytes(private_key_bytes)
        wallet_address = str(keypair.pubkey())
        encrypted_key = encrypt_private_key(private_key_bytes)

        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return None
        user.encrypted_private_key = encrypted_key
        user.wallet_address = wallet_address
        session.commit()
        return wallet_address
    except Exception:
        session.rollback()
        return None
    finally:
        session.close()
