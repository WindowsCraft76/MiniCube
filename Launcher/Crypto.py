import base64
import secrets
import keyring
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from Config import SALT_FILE

_KEYRING_SERVICE  = "MiniCube"
_KEYRING_USERNAME = "account_secret"
_FERNET: Fernet | None = None


def _get_or_create_secret() -> bytes:
    secret_hex = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    if secret_hex is None:
        secret_hex = secrets.token_bytes(32).hex()
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, secret_hex)
    return bytes.fromhex(secret_hex)


def _get_or_create_salt() -> bytes:
    if SALT_FILE.exists():
        return SALT_FILE.read_bytes()
    salt = secrets.token_bytes(16)
    SALT_FILE.write_bytes(salt)
    return salt


def _derive_fernet_key() -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_get_or_create_salt(),
        iterations=600_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(_get_or_create_secret()))


def _get_fernet() -> Fernet:
    global _FERNET
    if _FERNET is None:
        _FERNET = Fernet(_derive_fernet_key())
    return _FERNET


def encode_data(data: str) -> bytes:
    return _get_fernet().encrypt(data.encode("utf-8"))


def decode_data(data: bytes) -> str:
    return _get_fernet().decrypt(data).decode("utf-8")