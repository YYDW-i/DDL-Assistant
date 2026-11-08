"""Atomic user preferences; read legacy model setting for compatibility."""
import json
from . import config


def load_settings():
    path = config.data_dir() / "settings.json"
    if path.exists():
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(result, dict):
                return result
        except (ValueError, OSError):
            pass
    legacy = config.data_dir() / "settings.txt"
    if legacy.exists():
        for line in legacy.read_text(encoding="utf-8").splitlines():
            if line.startswith("model="):
                return {"model": line.split("=", 1)[1].strip()}
    return {}


def save_settings(**values):
    current = load_settings()
    current.update(values)
    path = config.data_dir() / "settings.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
