import os
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, jsonify, request

import config
import namer
import prep
import renamer
import scanner

MODELS = ["google/gemini-2.5-flash", "google/gemini-2.5-flash-lite", "openai/gpt-4o-mini", "anthropic/claude-sonnet-4"]
app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"))
JOBS, LOCK = {}, threading.Lock()


def status():
    c = config.load()
    return {"has_key": bool(c.get("key")), "model": c.get("model") or config.DEFAULT_MODEL, "models": MODELS}


def folder_or_400():
    f = str((request.get_json(silent=True) or {}).get("folder") or "")
    return f if f and Path(f).is_absolute() and Path(f).is_dir() else None


def thumb(item):
    try:
        return prep.thumb_b64(item["path"], item["kind"])
    except Exception:
        return ""


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/status")
def api_status():
    return jsonify(status())


@app.post("/api/settings")
def api_settings():
    config.save(**{k: v for k, v in request.get_json().items() if k in ("key", "model")})
    return jsonify(status())


@app.post("/api/check-key")
def api_check_key():
    return jsonify(namer.check_key(request.get_json().get("key") or config.load().get("key", "")))


@app.post("/api/scan")
def api_scan():
    f = folder_or_400()
    if not f:
        return jsonify(error="Not a folder"), 400
    items = scanner.scan(f)
    with ThreadPoolExecutor(8) as ex:
        thumbs = list(ex.map(thumb, items))
    return jsonify(items=[dict(i, thumb=t) for i, t in zip(items, thumbs)])


@app.post("/api/name")
def api_name():
    f = folder_or_400()
    if not f:
        return jsonify(error="Not a folder"), 400
    key = config.load().get("key")
    if not key and os.environ.get("SMART_EXPLORER_MOCK") != "1":
        return jsonify(error="Add your OpenRouter key in Settings"), 400
    items = scanner.scan(f)
    jid = uuid.uuid4().hex
    job = JOBS[jid] = {"done": False, "total": len(items), "progress": 0, "results": {}, "error": None}

    def on_progress(item_id, stage, proposed=None):
        with LOCK:
            job["progress"] += stage == "described"

    def work():
        try:
            out = namer.run(key, status()["model"], items, prep.encode, on_progress) if key else namer.mock_run(items, on_progress)
            # Keyed by absolute path, never by list position: this endpoint
            # re-scans the folder, so an index can point at a different file
            # than the browser is showing.
            job["results"] = {r["path"]: {"proposed": r["proposed"], "error": r.get("error")} for r in out}
        except Exception as e:
            job["error"] = str(e)
        job["done"] = True

    threading.Thread(target=work, daemon=True).start()
    return jsonify(job=jid)


@app.get("/api/name/<job>")
def api_name_poll(job):
    return jsonify(JOBS[job]) if job in JOBS else (jsonify(error="No such job"), 404)


@app.post("/api/rename")
def api_rename():
    return jsonify(renamer.apply(renamer.plan(request.get_json()["items"])))


@app.post("/api/undo")
def api_undo():
    jid = str(request.get_json().get("journal") or "")
    if not re.fullmatch(r"[0-9a-f]{32}", jid) or not (config.CONFIG_DIR / "journal" / (jid + ".json")).is_file():
        return jsonify(error="Nothing to undo"), 404
    return jsonify(restored=renamer.undo(jid))


@app.get("/api/pick-folder")
def api_pick_folder():
    try:
        import webview
        kind = webview.FileDialog.FOLDER if hasattr(webview, "FileDialog") else webview.FOLDER_DIALOG
        picked = webview.windows[0].create_file_dialog(kind)
    except Exception:
        picked = None
    return jsonify(folder=picked[0] if picked else None)
