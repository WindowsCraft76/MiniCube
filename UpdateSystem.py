import subprocess
import winreg
import re
from Config import PAGE_URL

### Functions to check for updates and compare versions.

def get_info_version():
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Mini Cube"

    try:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path)
        except FileNotFoundError:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)

        version, _ = winreg.QueryValueEx(key, "DisplayVersion")
        winreg.CloseKey(key)

        return str(version)

    except FileNotFoundError:
        try:
            return "No version found"
        except Exception as e:
            return f"Error reading fallback version: {e}"

    except Exception as e:
        return f"Registry error: {e}"

def get_remote_version():
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--sort=-v:refname", PAGE_URL + ".git"],
            capture_output=True,
            text=True,
            timeout=6,
            check=True
        )

        lines = result.stdout.strip().splitlines()
        if not lines:
            return "No tags found"

        for line in lines:
            tag_ref = line.split("\t")[1]
            tag_name = tag_ref.replace("refs/tags/", "").replace("^{}", "")

            if tag_name.lower().endswith("-dev"):
                continue

            return tag_name

        return "No stable tags found"

    except Exception as e:
        return f"Error fetching remote version: {e}"

def _normalize_version(version: str):
    version = version.strip().lower().lstrip("v")

    numbers = re.findall(r"\d+", version)

    if not numbers:
        return [0]

    return [int(n) for n in numbers]


def is_version_lower(local_version: str, remote_version: str) -> bool:
    try:
        local_parts = _normalize_version(local_version)
        remote_parts = _normalize_version(remote_version)

        length = max(len(local_parts), len(remote_parts))
        local_parts += [0] * (length - len(local_parts))
        remote_parts += [0] * (length - len(remote_parts))

        return local_parts < remote_parts

    except Exception:
        return False
    
def get_update_page_url(remote_version=None):
    if remote_version is None:
        remote_version = get_remote_version()

    if remote_version.endswith("-dev"):
        return PAGE_URL

    return f"{PAGE_URL}/releases/tag/{remote_version}"