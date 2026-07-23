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

CACHE_DIR     = DATA_DIR / "Cache"
SETTINGS_FILE = DATA_DIR / "settings.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.pem"
SALT_FILE     = DATA_DIR / ".salt"

for _d in [
    META_DIR, DATA_DIR, GAME_DIR, VERSIONS_DIR, ASSETS_DIR,
    LIBRARIES_DIR, INDEXES_DIR, OBJECTS_DIR, JAVA_DIR, NATIVES_DIR, LOGS_DIR,
    CACHE_DIR,
]:
    _d.mkdir(parents=True, exist_ok=True)

HEAD_ICON_SIZE = 64

CLIENT_ID_RPC = "1476290026626355231"

CLIENT_ID    = "e2341bbd-2575-4cf7-b913-f6372c1aaff1"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPE        = "XboxLive.signin offline_access"

AUTH_URL  = "https://login.live.com/oauth20_authorize.srf"
TOKEN_URL = "https://login.live.com/oauth20_token.srf"

XBOX_USER_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
XBOX_XSTS_URL      = "https://xsts.auth.xboxlive.com/xsts/authorize"

API_MCSERVICES_URL = "https://api.minecraftservices.com/"
API_AZUL_URL       = "https://api.azul.com"
API_URL            = "https://windowscraft76.fr/minicube/api"

VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
RESSOURCE_MC_URL     = "https://resources.download.minecraft.net"

PAGE_URL         = "https://windowscraft76.fr/minicube/"
DISCLAIMER_URL   = "https://windowscraft76.fr/minicube/r/disclaimer/"
TERMS_URL        = "https://windowscraft76.fr/minicube/r/terms/"
PRIVACY_URL      = "https://windowscraft76.fr/minicube/r/privacy/"
ISSUES_URL       = "https://windowscraft76.fr/minicube/r/issues/"
DOWNLOADLAST_URL = "https://windowscraft76.fr/minicube/r/downloadlast/"

copyright = "Copyright (c) 2026 WindowsCraft76"

REGISTRY_KEY_PATH   = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\MiniCube"
REGISTRY_VALUE_NAME = "DisplayVersion"

UPDATE_POPUP_MESSAGES = {
    "release": "A new version is available! ({version})\n\nDo you want to open the download page?",
    "hotfix": "A new patch version is available! ({version})\nIt is recommended to update as soon as possible.\n\nDo you want to open the download page?",
    "beta": "A new beta version is available! ({version})\n\nDo you want to open the download page?",
}
UPDATE_POPUP_MESSAGE_DEFAULT = "A new version is available! ({version})\n\nDo you want to open the download page?"