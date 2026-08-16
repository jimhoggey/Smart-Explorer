# Smart Explorer — Batch Rename (v1) design

## Goal
Desktop app (Windows primary, Mac too) that renames a folder of Canva-exported
slides/videos to content-based names (`Giving - Full Details.png`,
`Giving - Title Only.png`) using a vision model via OpenRouter, after the user
reviews the proposed names.

## Non-goals (v1)
Naming rules/hints, tool-shell/tile grid, OCR fallback, copying files elsewhere,
auto-updater, PDF input.

## Stack
Python 3.9+, Flask (localhost), pywebview window (browser fallback),
PyInstaller builds via GitHub Actions for mac + windows. Pillow for images,
imageio-ffmpeg for video frames, urllib for OpenRouter (no SDK). Key + model
stored in `~/.smart-explorer/config.json` (0600). Pattern lifted from
Service Visuals (`desktop.py`, `aiassist.py`).

## Modules
| file | responsibility |
|---|---|
| `scanner.py` | list supported files in a folder (png/jpg/jpeg/webp/mp4/mov), sorted by name |
| `prep.py` | image → ≤1024px JPEG base64; video → 3 frames (10/50/90%) → same |
| `namer.py` | two-stage OpenRouter pipeline; `MockNamer` for no-key/tests |
| `renamer.py` | sanitize names, resolve collisions ` (2)`, apply renames, journal, undo |
| `config.py` | read/write key + model |
| `app.py` | Flask routes + JSON API |
| `desktop.py` | window entry point |
| `static/index.html` (+ css/js) | single-page UI |

## AI pipeline (`namer.py`)
1. **Describe** — per file, one vision call (concurrency 5):
   image(s) + prompt → JSON `{kind, headline, details, has_details}`.
   Videos send 3 frames in one call.
2. **Name** — one text call with all descriptions + original names →
   JSON `[{index, name}]`. Instructions: short Title Case names from content;
   files of the same kind must be distinguished by what differs
   (`Giving - Full Details` vs `Giving - Title Only`); unique; no extension.
3. Failures: a describe failure marks that file "unnamed (keep original)";
   a name-stage failure falls back to `headline` per file with dedupe suffixes.
Default model `google/gemini-2.5-flash`; picker for others. `MockNamer`
returns deterministic names for tests / when no key.

## API
- `GET /api/status` → `{has_key, model}`; `POST /api/settings` `{key?, model?}`
- `POST /api/scan` `{folder}` → `[{id, path, name, kind, thumb}]`
- `POST /api/name` `{folder}` → SSE/poll: per-file `{id, proposed}` then done
- `POST /api/rename` `{folder, items:[{path,new_name}]}` → `{renamed, journal_id}`
- `POST /api/undo` `{journal_id}` → `{restored}`
- `GET /api/pick-folder` → native folder dialog via pywebview (fallback: text field)

## UI flow
Pick/drop folder → thumbnails grid → **Name with AI** (progress fills names in)
→ inline-edit any name → **Rename all** → toast + **Undo**. Gear icon: key,
model, test-key button. Dark, minimal, one screen.

## Renaming rules
Keep extension; strip `\/:*?"<>|` and control chars; trim to 100 chars;
if target exists or duplicates in batch → ` (2)`, ` (3)`; skip unchanged.
Journal `~/.smart-explorer/journal/<id>.json` = `[[old,new],...]`; undo
reverses in reverse order, skipping entries whose `new` no longer exists.

## Testing
pytest: prep (image resize, video frames on a generated clip), renamer
(sanitize/collision/undo on tmp dir), namer JSON parsing + fallback with a
stubbed HTTP, end-to-end app test with `MockNamer` on tmp folder.
Manual: real key on Windows + Mac.

## Packaging
`.github/workflows/build.yml`: on `v*` tag build with PyInstaller on
`windows-latest` and `macos-latest`, upload zips. Windows tested first.
