import os
from pathlib import Path

CONTENT       = Path(__file__).resolve().parent.parent / "Content"

BASE_DIR      = Path(os.path.expandvars(r"%appdata%")) / ".MiniCube"
META_DIR      = BASE_DIR / "Meta"
GAME_DIR      = BASE_DIR / "GameFile"
DATA_DIR      = BASE_DIR / "Data"
LOGS_DIR      = BASE_DIR / "Logs"

VERSIONS_DIR  = META_DIR / "versions"
ASSETS_DIR    = META_DIR / "assets"
LIBRARIES_DIR = META_DIR / "libraries"
INDEXES_DIR   = ASSETS_DIR / "indexes"
OBJECTS_DIR   = ASSETS_DIR / "objects"
JAVA_DIR      = META_DIR / "java_versions"
NATIVES_DIR   = META_DIR / "natives"

SETTINGS_FILE = DATA_DIR / "settings.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.pem"
SALT_FILE     = DATA_DIR / ".salt"

for _d in [
    META_DIR, DATA_DIR, GAME_DIR, VERSIONS_DIR, ASSETS_DIR,
    LIBRARIES_DIR, INDEXES_DIR, OBJECTS_DIR, JAVA_DIR, NATIVES_DIR, LOGS_DIR,
]:
    _d.mkdir(parents=True, exist_ok=True)

CLIENT_ID_RPC = "1476290026626355231"

CLIENT_ID    = "e2341bbd-2575-4cf7-b913-f6372c1aaff1"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPE        = "XboxLive.signin offline_access"

AUTH_URL  = "https://login.live.com/oauth20_authorize.srf"
TOKEN_URL = "https://login.live.com/oauth20_token.srf"

XBOX_USER_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
XBOX_XSTS_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"

API_MCSERVICES_URL = "https://api.minecraftservices.com/"
API_AZUL_URL         = "https://api.azul.com"
API_GITHUB_URL       = "https://api.github.com"

VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
RESSOURCE_MC_URL     = "https://resources.download.minecraft.net"
PAGE_URL             = "https://github.com/WindowsCraft76/MiniCube"

copyright = "Copyright (c) 2026 WindowsCraft76"