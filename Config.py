import base64
from pathlib import Path

### Configuration constants and utility functions for the Mini Cube application.

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

for d in [DATA_DIR, GAME_DIR, VERSIONS_DIR, ASSETS_DIR, LIBRARIES_DIR, INDEXES_DIR, OBJECTS_DIR, JAVA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

OBFUSCATION_KEY: bytes = b"my_secret_key"  # Key for XOR obfuscation of account data

# Microsoft authentication
CLIENT_ID = "e2341bbd-2575-4cf7-b913-f6372c1aaff1"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPE = "XboxLive.signin offline_access"

# URLs and version management
VERSION_MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
PAGE_URL = "https://github.com/WindowsCraft76/mini-cube"

# Utility function to center a Tkinter window on the screen
def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")

# XOR-based obfuscation for account data
def xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

def encode_data(data: str, key: bytes) -> bytes:
    xored = xor_bytes(data.encode("utf-8"), key)
    return base64.b64encode(xored)

def decode_data(data: bytes, key: bytes) -> str:
    xored = base64.b64decode(data)
    return xor_bytes(xored, key).decode("utf-8")
