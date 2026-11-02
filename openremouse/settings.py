"""User settings stored in %APPDATA%\OpenReMouse\settings.json (theme, language)."""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "OpenReMouse"
SETTINGS_FILE = CONFIG_DIR / "settings.json"


def load() -> dict:
    try:
        d = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save(**kv) -> None:
    """Merge ``kv`` into the settings file (other keys are kept)."""
    d = load()
    d.update(kv)
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass
