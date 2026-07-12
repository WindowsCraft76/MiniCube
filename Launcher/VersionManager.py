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


def type_to_suffix(version_type: str) -> str:
    if not version_type:
        return ""
    return TYPE_SUFFIXES.get(version_type.lower(), "")

def get_info_version() -> str:
    raw_version = read_local_version()
    return format_local_version_for_display(raw_version)

def _fetch_remote_data(beta_fallback: bool = True):
    response = requests.get(
        API_URL,
        params={"query": "version"},
        timeout=5,
    )
    response.raise_for_status()
    data = response.json()

    last = data.get("last", {})
    if not isinstance(last, dict):
        return None, None

    has_release = bool(last.get("version"))

    if has_release:
        raw_number = last.get("version", "")
        suffix = type_to_suffix(last.get("type", ""))
    else:
        if not beta_fallback:
            return None, None

        last_beta = last.get("beta", {})
        if not isinstance(last_beta, dict):
            last_beta = {}

        raw_number = last_beta.get("version", "")
        suffix = type_to_suffix(last_beta.get("type", ""))

    clean_number = strip_version_decorators(raw_number)
    if not clean_number:
        return None, None

    return clean_number, suffix


def get_remote_version(beta_fallback: bool = True) -> str:
    try:
        clean_number, _suffix = _fetch_remote_data(beta_fallback=beta_fallback)
        if not clean_number:
            return "No version found"
        return clean_number

    except Exception as e:
        return f"Error fetching remote version: {e}"

def get_remote_display_version(beta_fallback: bool = True) -> str:
    try:
        clean_number, suffix = _fetch_remote_data(beta_fallback=beta_fallback)
        if not clean_number:
            return "No version found"
        return f"v{clean_number}{suffix}"

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
    local_display_version = format_local_version_for_display(local_raw_version)

    try:
        remote_numeric, suffix = _fetch_remote_data(beta_fallback=beta_fallback)
        remote_display_version = (
            f"v{remote_numeric}{suffix}" if remote_numeric else "No version found"
        )
        remote_numeric = remote_numeric or "No version found"
    except Exception as e:
        remote_numeric = f"Error fetching remote version: {e}"
        remote_display_version = remote_numeric

    update_available, is_first_install = compare_versions(local_raw_version, remote_numeric)

    return {
        "local_raw_version": local_raw_version,
        "local_display_version": local_display_version,
        "remote_version": remote_numeric,
        "remote_display_version": remote_display_version,
        "update_available": update_available,
        "is_first_install": is_first_install,
    }


def get_update_page_url():
    return DOWNLOADLAST_URL