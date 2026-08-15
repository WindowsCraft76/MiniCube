import re
import requests

from Config import API_URL, DOWNLOADLAST_URL, REGISTRY_KEY_PATH, REGISTRY_VALUE_NAME

try:
    import winreg
except ImportError:
    winreg = None

TYPE_SUFFIXES = {
    "release": "r",
    "hotfix": "h",
    "beta": "b",
}

SUFFIX_TO_TYPE = {v: k for k, v in TYPE_SUFFIXES.items()}

def _query_registry(use32bit_view: bool = False) -> str:
    if winreg is None:
        return ""

    access_flag = winreg.KEY_WOW64_32KEY if use32bit_view else winreg.KEY_WOW64_64KEY

    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            REGISTRY_KEY_PATH,
            0,
            winreg.KEY_READ | access_flag,
        )
        try:
            value, _ = winreg.QueryValueEx(key, REGISTRY_VALUE_NAME)
        finally:
            winreg.CloseKey(key)

        return str(value).strip()

    except FileNotFoundError:
        return ""
    except Exception:
        return ""


def read_local_version() -> str:
    result = _query_registry(use32bit_view=False)
    if result:
        return result

    result = _query_registry(use32bit_view=True)
    if result:
        return result

    return ""

def strip_version_decorators(raw: str) -> str:
    if not raw:
        return ""
    s = raw.lstrip("vV")
    s = re.sub(r"-dev$", "", s, flags=re.IGNORECASE)
    return re.sub(r"[a-zA-Z]+$", "", s).strip()


def type_to_suffix(version_type: str) -> str:
    if not version_type:
        return ""
    return TYPE_SUFFIXES.get(version_type.lower(), "")


def get_local_suffix(numeric_version: str) -> str:
    if not numeric_version:
        return ""

    parts = numeric_version.split(".")

    if len(parts) >= 3:
        try:
            if int(parts[2]) > 0:
                return "h"
        except ValueError:
            pass

    if len(parts) >= 2:
        try:
            if int(parts[1]) > 0:
                return "b"
        except ValueError:
            pass

    return "r"


def get_local_version_type(numeric_version: str) -> str:
    if not numeric_version:
        return "None"
    suffix = get_local_suffix(numeric_version)
    return SUFFIX_TO_TYPE.get(suffix, "release").capitalize()


def format_local_version_for_display(numeric_version: str) -> str:
    if not numeric_version:
        return "Version not found!"
    return f"v{numeric_version}{get_local_suffix(numeric_version)}"


def get_info_version() -> str:
    raw_version = read_local_version()
    return format_local_version_for_display(raw_version)

def _fetch_remote_catalog() -> dict:
    response = requests.get(API_URL, params={"query": "version"}, timeout=5)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def _resolve_entry(catalog: dict, ref):
    if not isinstance(ref, dict):
        return None

    raw_number = ref.get("version", "")
    number = strip_version_decorators(raw_number)
    if not number:
        return None

    versions = catalog.get("version", {})
    if not isinstance(versions, dict):
        versions = {}
    info = versions.get(raw_number) or versions.get(number) or {}

    version_type = info.get("type", "")
    display = info.get("display") or f"v{number}{type_to_suffix(version_type)}"
    return number, version_type, display


def _last_entry(catalog: dict, beta_fallback: bool = True):
    last = catalog.get("last", {})
    if not isinstance(last, dict):
        return None

    entry = _resolve_entry(catalog, last.get("release"))
    if entry:
        return entry

    if beta_fallback:
        return _resolve_entry(catalog, last.get("beta"))

    return None


def get_remote_version(beta_fallback: bool = True) -> str:
    try:
        catalog = _fetch_remote_catalog()
        entry = _last_entry(catalog, beta_fallback)
        if not entry:
            return "No version found"
        return entry[0]

    except Exception as e:
        return f"Error fetching remote version: {e}"


def get_remote_display_version(beta_fallback: bool = True) -> str:
    try:
        catalog = _fetch_remote_catalog()
        entry = _last_entry(catalog, beta_fallback)
        if not entry:
            return "No version found"
        return entry[2]

    except Exception as e:
        return f"Error fetching remote version: {e}"


def _parse_version(version_str: str):
    if not version_str:
        return None
    try:
        return tuple(int(p) for p in version_str.split("."))
    except ValueError:
        return None


def is_version_lower(local_version: str, remote_version: str) -> bool:
    local_clean = strip_version_decorators(local_version)
    remote_clean = strip_version_decorators(remote_version)

    local_parts = _parse_version(local_clean)
    remote_parts = _parse_version(remote_clean)

    if remote_parts is None:
        return False

    if local_parts is None:
        return True

    length = max(len(local_parts), len(remote_parts))
    local_parts += (0,) * (length - len(local_parts))
    remote_parts += (0,) * (length - len(remote_parts))

    return local_parts < remote_parts


def compare_versions(local_raw_version: str, remote_version: str):
    local_numeric = strip_version_decorators(local_raw_version)
    remote_numeric = _parse_version(remote_version)

    if not local_numeric:
        return True, True

    if remote_numeric is None:
        return False, False

    if is_version_lower(local_numeric, remote_version):
        return True, False

    return False, False


def check_for_update(beta_fallback: bool = True):
    local_raw_version = read_local_version()
    local_key = strip_version_decorators(local_raw_version) or local_raw_version

    remote_type = "None"
    local_display_version = format_local_version_for_display(local_raw_version)

    try:
        catalog = _fetch_remote_catalog()
        entry = _last_entry(catalog, beta_fallback)

        if entry:
            remote_numeric, version_type, remote_display_version = entry
            remote_type = (version_type or "release").capitalize()
        else:
            remote_numeric = "No version found"
            remote_display_version = "No version found"

        local_entry = catalog.get("version", {}).get(local_key)
        if isinstance(local_entry, dict) and local_entry.get("display"):
            local_display_version = local_entry["display"]

    except Exception as e:
        remote_numeric = f"Error fetching remote version: {e}"
        remote_display_version = remote_numeric

    update_available, is_first_install = compare_versions(local_raw_version, remote_numeric)

    return {
        "local_raw_version": local_raw_version,
        "local_display_version": local_display_version,
        "remote_version": remote_numeric,
        "remote_display_version": remote_display_version,
        "remote_type": remote_type,
        "update_available": update_available,
        "is_first_install": is_first_install,
    }


def get_update_page_url():
    return DOWNLOADLAST_URL