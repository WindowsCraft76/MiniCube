import json
from Config import LANG_DIR

class I18n:
    def __init__(self, default="en_us"):
        self.lang_dir = LANG_DIR
        self.default_language = default
        self.strings = {}
        self.default_strings = self._load(default)
        available = self.available()
        if default in available:
            self.set_language(default)
        else:
            self.current = default
            self.strings = self.default_strings

    def _load(self, code):
        path = self.lang_dir / f"{code}.json"
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def available(self):
        return sorted(p.stem for p in self.lang_dir.glob("*.json"))

    def display_name(self, code):
        path = self.lang_dir / f"{code}.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        name = data.get("language_name") if isinstance(data, dict) else None
        return name.strip() if isinstance(name, str) and name.strip() else path.name

    def set_language(self, code):
        if code not in self.available():
            code = self.default_language
        self.strings = self._load(code)
        self.current = code

    def t(self, key, **kwargs):
        text = (
            self.strings.get(key)
            or self.default_strings.get(key)
            or key
        )
        return text.format(**kwargs) if kwargs else text

i18n = I18n()
t = i18n.t