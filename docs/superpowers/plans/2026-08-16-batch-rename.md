# Batch Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Desktop app that proposes content-based names for a folder of slide images/videos via OpenRouter, lets the user review/edit, renames in place with undo.

**Architecture:** Flask on localhost + pywebview window; small pure-Python modules (scanner, prep, namer, renamer, config) each unit-tested; one static HTML page.

**Tech Stack:** Python 3.9+, Flask, Pillow, imageio-ffmpeg, pywebview, pytest, PyInstaller. HTTP via urllib (no SDK).

## Global Constraints
- Spec: `docs/superpowers/specs/2026-08-16-batch-rename-design.md` — read it first.
- **Minimal code.** No abstractions for one caller, no classes where a function does, no comments restating code. Every function ≤ ~25 lines.
- Python 3.9 compatible (no `match`, no `X | Y` types). Windows-first: use `pathlib`, no shell calls, no POSIX-only APIs (`chmod` guarded by try/except).
- Config dir: `~/.smart-explorer/`. Supported extensions: `.png .jpg .jpeg .webp .mp4 .mov`.
- Tests: `pytest -q` from repo root; tests in `tests/`, no network — stub `urllib.request.urlopen`.
- Commit after each task: `git add -A && git commit -qm "<msg>"`.

---

### Task 1: scanner + config + renamer (independent pure modules)

**Files:** Create `scanner.py`, `config.py`, `renamer.py`, `tests/test_core.py`, `requirements.txt` (`flask>=3.0 pillow>=10.0 imageio-ffmpeg>=0.5 pywebview>=5.0 pytest`).

**Produces:**
```python
# scanner.py
EXTS = {".png",".jpg",".jpeg",".webp",".mp4",".mov"}
def scan(folder: str) -> list[dict]   # [{id:int, path:str, name:str, kind:"image"|"video"}], sorted by name (case-insensitive), non-recursive
# config.py
CONFIG_DIR: Path; DEFAULT_MODEL = "google/gemini-2.5-flash"
def load() -> dict            # {} if missing/corrupt
def save(**kv) -> dict        # merge + write (mkdir parents, try chmod 0600), returns merged
# renamer.py
def sanitize(name: str, ext: str) -> str      # strip \/:*?"<>| and control chars, collapse spaces, trim, ≤100 chars + ext; empty → "Untitled"+ext
def plan(items: list[dict]) -> list[tuple[str,str]]  # items [{path,new_name}] → [(old,new)] with new = sanitized, collisions vs disk and within batch → " (2)", " (3)"; unchanged names skipped
def apply(pairs, journal_dir=CONFIG_DIR/"journal") -> str   # os.rename each; write <id>.json = [[old,new],...]; return id (uuid4 hex)
def undo(journal_id, journal_dir=...) -> int  # reverse order, skip if new missing or old exists; return count restored; delete journal
```

**Tests (write first, all in `tests/test_core.py`):**
- `scan`: tmp folder with `b.PNG, a.mp4, c.txt, sub/x.png` → 2 items ordered `a.mp4 (video)`, `b.PNG (image)`.
- `config`: `save(key="k")` then `load()["key"]=="k"`; corrupt file → `{}` (monkeypatch `CONFIG_DIR`).
- `sanitize("Giving: Full/Details?", ".png") == "Giving Full Details.png"`; empty → `Untitled.png`; 200-char name trimmed to 100 + ext.
- `plan`: two items both → `Giving` with `Giving.png` already on disk → `Giving (2).png`, `Giving (3).png`; item whose sanitized name equals current name → not in result.
- `apply`+`undo` on tmp dir: files renamed, journal exists, `undo` restores both, returns 2, journal removed.

Steps: write tests → run (`pytest -q`, expect ImportError) → implement → pass → commit `feat: scanner, config, renamer`.

---

### Task 2: prep (image/video → base64 JPEG)

**Files:** Create `prep.py`, `tests/test_prep.py`.

**Produces:**
```python
def image_b64(path: str, max_side=1024) -> str        # RGB, thumbnail(max_side), JPEG q80 → base64 str (no data: prefix)
def video_frames_b64(path: str, n=3, max_side=1024) -> list[str]  # frames at 10/50/90% via imageio_ffmpeg.read_frames; graceful: fewer frames if short
def thumb_b64(path: str, kind: str) -> str            # 240px thumb for the UI: image → image_b64(path,240); video → first of video_frames_b64(path,1,240)
def encode(item: dict) -> list[str]                   # kind image → [image_b64]; video → video_frames_b64
```
Use `imageio_ffmpeg.read_frames(path)`; first yielded item is meta (`size`, `fps`, `duration`); pick frame indices from `duration*fps`. Iterate once, keep only needed frames.

**Tests:** create a 2000×1000 PNG with Pillow → `image_b64` decodes to JPEG ≤1024 wide. Video: generate a 1-second 64×64 mp4 with `imageio_ffmpeg.write_frames` in a fixture (skip test if ffmpeg unavailable) → `video_frames_b64` returns 3 strings. `encode` dispatches by kind.

Commit `feat: prep`.

---

### Task 3: namer (OpenRouter two-stage pipeline + mock)

**Files:** Create `namer.py`, `tests/test_namer.py`.

**Produces:**
```python
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
class NamerError(Exception): ...
def chat(key, model, messages, timeout=90) -> str      # urllib POST, headers Authorization Bearer + HTTP-Referer/X-Title "Smart Explorer"; returns content str; raise NamerError with plain-English message on HTTP/network/JSON errors
def parse_json(text) -> object                          # strip ```json fences, find first {..} or [..], json.loads
def describe(key, model, item, images: list[str]) -> dict   # vision call, returns {kind, headline, details, has_details}; on failure → {"error": msg}
def name_all(descs: list[dict]) -> list[str]           # text call: input [{index, original, **desc}] → returns names list aligned to input; fallback: headline or original stem, deduped " (2)"
def run(key, model, items, encode, on_progress=None) -> list[dict]  # items from scanner; concurrency 5 (ThreadPoolExecutor); calls on_progress(item_id, stage, proposed?) ; returns [{id, proposed, error?}]
def check_key(key) -> dict                             # GET https://openrouter.ai/api/v1/key → {ok, label?, error?}
def mock_run(items, encode=None, on_progress=None)     # deterministic: "Slide 1", "Slide 2"... (same signature shape minus key/model)
```
Prompts (keep verbatim, they are the product):
- describe (system): `You describe church presentation slides. Reply ONLY with JSON: {"kind": short category like Giving, Announcement, Sermon Title, Worship Lyrics, Countdown, Welcome, Background; "headline": the main visible text; "details": other visible text/details in one line, or ""; "has_details": true/false}`
- name (system): `You name slide files from their descriptions. Reply ONLY with a JSON array of strings, one per input, same order. Rules: short Title Case name based on content, like "Giving - Full Details" or "Sermon Title - Anchored Week 3". When several inputs share a kind, distinguish them by what differs (details vs title only, different text, etc.). Never repeat a name. No file extensions, no numbering unless it is on the slide.`

**Tests (stub `namer.urlopen` via monkeypatch to return canned OpenAI-format JSON):** `parse_json` handles fenced/prefixed text; `describe` returns dict, and error dict on exception; `name_all` fallback dedupes when call raises; `run` with a fake `chat` returns aligned proposals and calls `on_progress`; `mock_run` deterministic.

Commit `feat: namer pipeline`.

---

### Task 4: Flask app + UI

**Files:** Create `app.py`, `static/index.html`, `static/app.js`, `static/style.css`, `tests/test_app.py`.

**Routes (JSON):**
- `GET /` → index.html
- `GET /api/status` → `{has_key, model, models:[...]}`
- `POST /api/settings` `{key?, model?}` → status; `POST /api/check-key` → `check_key` result
- `POST /api/scan` `{folder}` → `{items:[{id,path,name,kind,thumb}]}` (400 if not a dir)
- `POST /api/name` `{folder}` → starts a thread; returns `{job}`; `GET /api/name/<job>` → `{done, results:{id:{proposed,error}}}` (poll every 700ms). No key and `SMART_EXPLORER_MOCK=1` → `mock_run`; no key otherwise → 400 `"Add your OpenRouter key in Settings"`.
- `POST /api/rename` `{items:[{path,new_name}]}` → `{renamed:n, journal}`; `POST /api/undo` `{journal}` → `{restored:n}`
- `GET /api/pick-folder` → uses `webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)` if a window exists, else `{folder:null}` (UI shows a text field fallback).

**UI (single dark screen, vanilla JS, no framework, ≤ 200 lines JS):** header (title, gear); folder row (Pick folder / path input, Name with AI, Rename all, Undo); grid of cards: thumb, original name (muted), editable input for proposed name; progress bar during naming; toast for results; settings dialog (`<dialog>`): key, model select (Gemini 2.5 Flash / Flash Lite / GPT-4o-mini / Claude Sonnet / custom), Test key, Save. Style: system font, `#0b0c0e` bg, one accent.

**Tests (Flask test client, tmp folder, monkeypatch config dir, `SMART_EXPLORER_MOCK=1`):** scan returns items with thumbs; name → poll until done → proposals; rename applies and undo restores.

Commit `feat: app + ui`.

---

### Task 5: desktop entry, run scripts, packaging, CI

**Files:** Create `desktop.py` (port pick, Flask in thread, pywebview window 1200×820, browser fallback, `SMART_EXPLORER_HEADLESS`), `run.sh`, `run.bat` (create venv, install, `python desktop.py`), `smart_explorer.spec` (PyInstaller onedir, includes `static/`, imageio_ffmpeg binary via `collect_data_files`), `.github/workflows/build.yml` (on `v*` tag: matrix windows-latest/macos-latest, `pip install -r requirements.txt pyinstaller`, `pyinstaller smart_explorer.spec`, headless smoke `SMART_EXPLORER_HEADLESS=1` start + curl `/api/status`, zip `dist/`, upload artifact/release), `README.md` (install on Windows/Mac, get an OpenRouter key, usage, run from source).

**Verify:** `python desktop.py` opens window locally (or headless prints URL); `pytest -q` green. Commit `feat: desktop + packaging`.

---

## Self-review
- Spec coverage: scanner/prep/namer/renamer/config/app/desktop/UI/undo/journal/packaging/tests all mapped (T1–T5). ✔
- No placeholders; interfaces named consistently (`scan`, `encode`, `run`, `mock_run`, `plan`, `apply`, `undo`, `check_key`). ✔
