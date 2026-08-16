import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".smart-explorer"
DEFAULT_MODEL = "google/gemini-2.5-flash"


def load():
    try:
        return json.loads((CONFIG_DIR / "config.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def save(**kv):
    data = {**load(), **kv}
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = CONFIG_DIR / "config.json"
    path.write_text(json.dumps(data), "utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return data
