import json
from datetime import datetime, timezone
from Config import LAUNCHER_PROFILES_FILE


def _now_iso():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


class ProfileManager:

    def __init__(self, path=LAUNCHER_PROFILES_FILE):
        self.path = path

    def ensure_file(self):
        if not self.path.exists():
            self._save({})

    def _load(self):
        if not self.path.exists():
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return {}
        return data.get("profiles", {})

    def _save(self, profiles):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"profiles": profiles}, f, indent=4)

    def has_profile(self, version_id):
        return version_id in self._load()

    def get_all_profiles(self):
        profiles = self._load()
        changed = False
        for profile in profiles.values():
            if "type" not in profile:
                profile["type"] = "custom"
                changed = True
        if changed:
            self._save(profiles)
        return profiles

    def get_profile(self, version_id):
        return self._load().get(version_id)

    def create_or_update(self, version_id, profile_type="vanilla", **extra_fields):
        profiles = self._load()
        profile = profiles.get(version_id, {})
        profile["lastUsed"] = _now_iso()
        profile["lastVersionId"] = version_id
        profile["type"] = profile_type
        profile.update(extra_fields)
        profiles[version_id] = profile
        self._save(profiles)

    def remove_profile(self, version_id):
        profiles = self._load()
        if version_id in profiles:
            del profiles[version_id]
            self._save(profiles)