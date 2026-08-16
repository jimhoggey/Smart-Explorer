import base64
import io

import pytest
from PIL import Image

import prep


def _decode(b64):
    return Image.open(io.BytesIO(base64.b64decode(b64)))


@pytest.fixture
def png(tmp_path):
    p = tmp_path / "big.png"
    Image.new("RGBA", (2000, 1000), (255, 0, 0, 255)).save(p)
    return str(p)


@pytest.fixture
def mp4(tmp_path):
    import imageio_ffmpeg

    try:
        imageio_ffmpeg.get_ffmpeg_exe()
    except RuntimeError:
        pytest.skip("ffmpeg unavailable")
    p = tmp_path / "clip.mp4"
    w = imageio_ffmpeg.write_frames(str(p), (64, 64), fps=10)
    w.send(None)
    for i in range(10):
        w.send(bytes([i * 20]) * (64 * 64 * 3))
    w.close()
    return str(p)


def test_image_b64(png):
    img = _decode(prep.image_b64(png))
    assert img.format == "JPEG"
    assert img.width <= 1024 and img.height <= 512


def test_video_frames_b64(mp4):
    frames = prep.video_frames_b64(mp4)
    assert len(frames) == 3
    assert all(_decode(f).format == "JPEG" for f in frames)


def test_thumb_b64(png, mp4):
    assert _decode(prep.thumb_b64(png, "image")).width <= 240
    assert _decode(prep.thumb_b64(mp4, "video")).width <= 240


def test_encode(png, mp4):
    assert len(prep.encode({"path": png, "kind": "image"})) == 1
    assert len(prep.encode({"path": mp4, "kind": "video"})) == 3
