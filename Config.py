# Configuration file for Mini Cube Launcher

import base64
import secrets
from pathlib import Path
import keyring
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# Define paths for game files, data, and content
BASE_DIR = Path(__file__).resolve().parent
GAME_DIR = BASE_DIR / "GameFile"
DATA_DIR = BASE_DIR / "Data"
CONTENT = BASE_DIR / "Content"

VERSIONS_DIR = GAME_DIR / "versions"
ASSETS_DIR = GAME_DIR / "assets"
LIBRARIES_DIR = GAME_DIR / "libraries"
INDEXES_DIR = ASSETS_DIR / "indexes"
OBJECTS_DIR = ASSETS_DIR / "objects"
JAVA_DIR = GAME_DIR / "java_versions"

SETTINGS_FILE = DATA_DIR / "settings.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
SALT_FILE = DATA_DIR / ".salt"

for d in [DATA_DIR, GAME_DIR, VERSIONS_DIR, ASSETS_DIR, LIBRARIES_DIR, INDEXES_DIR, OBJECTS_DIR, JAVA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Discord Rich Presence
CLIENT_ID_RPC = "1476290026626355231"

# Microsoft authentication
CLIENT_ID = "e2341bbd-2575-4cf7-b913-f6372c1aaff1"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPE = "XboxLive.signin offline_access"

# URLs and version management
VERSION_MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
PAGE_URL = "https://github.com/WindowsCraft76/mini-cube"


#  Secure key management
_KEYRING_SERVICE = "MiniCubeLauncher"
_KEYRING_USERNAME = "account_secret"

# Functions for secure key management and encryption/decryption of sensitive data.
def _get_or_create_secret() -> bytes:
    secret_hex = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)

    if secret_hex is None:
        raw_secret = secrets.token_bytes(32)
        secret_hex = raw_secret.hex()
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, secret_hex)

    return bytes.fromhex(secret_hex)

def _get_or_create_salt() -> bytes:
    if SALT_FILE.exists():
        return SALT_FILE.read_bytes()

    salt = secrets.token_bytes(16)
    SALT_FILE.write_bytes(salt)
    return salt

def _derive_fernet_key() -> bytes:
    secret = _get_or_create_secret()
    salt = _get_or_create_salt()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    raw_key = kdf.derive(secret)
    return base64.urlsafe_b64encode(raw_key)

def _get_fernet() -> "Fernet":
    return Fernet(_derive_fernet_key())

def encode_data(data: str, key: bytes = None) -> bytes:
    return _get_fernet().encrypt(data.encode("utf-8"))


def decode_data(data: bytes, key: bytes = None) -> str:
    return _get_fernet().decrypt(data).decode("utf-8")


# Center window
def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")