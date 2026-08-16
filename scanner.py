from pathlib import Path

EXTS = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov"}
VIDEO = {".mp4", ".mov"}


def scan(folder):
    files = [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in EXTS and not p.name.startswith(".")]
    files.sort(key=lambda p: p.name.lower())
    return [{"id": i, "path": str(p), "name": p.name,
             "kind": "video" if p.suffix.lower() in VIDEO else "image"} for i, p in enumerate(files)]
