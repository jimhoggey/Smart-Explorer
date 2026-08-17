# Smart Explorer

Renames a folder of exported slides (`.png .jpg .jpeg .webp .mp4 .mov`) to content-based names like `Giving - Full Details.png`, using a vision model via OpenRouter. You review and edit every name before anything is renamed, and there is an Undo.

## Install

**Windows:** download `SmartExplorer-Windows.zip` from the latest [release](../../releases), unzip anywhere, run `SmartExplorer\SmartExplorer.exe`. If SmartScreen warns, click *More info → Run anyway*.

**Mac:** download `SmartExplorer-macOS.zip`, unzip, drag **SmartExplorer.app** to Applications. The app is ad-hoc signed, not notarised, so macOS quarantines it on first download — clear that once in Terminal, then open it normally:

```
xattr -dr com.apple.quarantine /Applications/SmartExplorer.app
```

## Get an OpenRouter key

1. Sign up at [openrouter.ai](https://openrouter.ai) and add a few dollars of credit.
2. Create a key under *Keys*.
3. In Smart Explorer click the gear, paste the key, pick a model (default: Gemini 2.5 Flash), *Test key*, *Save*.

The key is stored in `~/.smart-explorer/config.json`. Nothing is sent anywhere except OpenRouter.

## Use

1. **Pick folder** (or paste a path).
2. **Name with AI** — proposed names fill in as files are processed.
3. Edit any name inline.
4. **Rename all** — files are renamed in place; **Undo** reverts the last batch.

Names are sanitized for Windows, capped at 100 characters, and get ` (2)`, ` (3)` on collisions. Undo journals live in `~/.smart-explorer/journal/`.

## Run from source

Requires Python 3.9+.

- Windows: double-click `run.bat`
- Mac/Linux: `./run.sh`

Both create `.venv`, install `requirements.txt`, and start `desktop.py`. `SMART_EXPLORER_HEADLESS=1 python desktop.py` prints a URL to open in a browser instead of a window; `SMART_EXPLORER_MOCK=1` names files without a key (for testing).

Tests: `python -m pytest -q`. Build: `pip install pyinstaller && pyinstaller smart_explorer.spec` → `dist/SmartExplorer/`. Pushing a `v*` tag builds Windows and Mac zips via GitHub Actions.
