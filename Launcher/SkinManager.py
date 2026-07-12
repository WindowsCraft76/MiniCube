from io import BytesIO
from pathlib import Path
import requests
from PIL import Image
from Config import CACHE_DIR, HEAD_ICON_SIZE

def _build_head_image(skin_image: Image.Image) -> Image.Image:
    skin_image = skin_image.convert("RGBA")

    head = skin_image.crop((8, 8, 16, 16)).copy()

    try:
        overlay = skin_image.crop((40, 8, 48, 16))
        head.alpha_composite(overlay)
    except Exception:
        pass

    return head.resize((HEAD_ICON_SIZE, HEAD_ICON_SIZE), Image.NEAREST)


def fetch_and_cache_head(uuid: str, skin_url: str, app=None) -> Path | None:
    if not uuid or not skin_url:
        return None

    try:
        r = requests.get(skin_url, timeout=10)
        r.raise_for_status()

        skin_image = Image.open(BytesIO(r.content))
        head = _build_head_image(skin_image)

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        head_path = CACHE_DIR / f"{uuid}.png"
        head.save(head_path, format="PNG")

        if app:
            app.log(f"Player head cached for {uuid}.", "info")

        return head_path

    except Exception as e:
        if app:
            app.log(f"Failed to cache player head: {e}", "warn")
        return None


def get_cached_head_path(uuid: str):
    if not uuid:
        return None
    path = CACHE_DIR / f"{uuid}.png"
    return path if path.exists() else None