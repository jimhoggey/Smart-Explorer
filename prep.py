import base64
import io

import imageio_ffmpeg
from PIL import Image


def _jpeg_b64(img, max_side):
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def image_b64(path, max_side=1024):
    return _jpeg_b64(Image.open(path), max_side)


def video_frames_b64(path, n=3, max_side=1024):
    gen = imageio_ffmpeg.read_frames(path)
    meta = next(gen)
    total = max(int(meta["duration"] * meta["fps"]), 1)
    wanted = sorted({min(int(total * f), total - 1) for f in (0.1, 0.5, 0.9)[:n]})
    out = []
    try:
        for i, frame in enumerate(gen):
            if i in wanted:
                out.append(_jpeg_b64(Image.frombytes("RGB", meta["size"], frame), max_side))
            if i >= wanted[-1]:
                break
    finally:
        gen.close()
    if not out:
        raise ValueError("No frames decoded from %s" % path)
    return out


def thumb_b64(path, kind):
    return image_b64(path, 240) if kind == "image" else video_frames_b64(path, 1, 240)[0]


def encode(item):
    return [image_b64(item["path"])] if item["kind"] == "image" else video_frames_b64(item["path"])
