import time

import pytest
from PIL import Image

import config


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setenv("SMART_EXPLORER_MOCK", "1")
    import app
    app.app.testing = True
    return app.app.test_client()


@pytest.fixture
def folder(tmp_path):
    d = tmp_path / "slides"
    d.mkdir()
    for n in ["b.png", "a.jpg"]:
        Image.new("RGB", (400, 200), "red").save(d / n)
    (d / "notes.txt").write_text("x")
    return d


def test_status_and_settings(client):
    s = client.get("/api/status").get_json()
    assert s["has_key"] is False and s["model"] == config.DEFAULT_MODEL and s["models"]
    s = client.post("/api/settings", json={"key": "sk", "model": "m"}).get_json()
    assert s["has_key"] is True and s["model"] == "m"


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200 and b"<html" in r.data


def test_scan(client, folder):
    assert client.post("/api/scan", json={"folder": str(folder / "nope")}).status_code == 400
    assert client.post("/api/scan", json={"folder": "."}).status_code == 400
    items = client.post("/api/scan", json={"folder": str(folder)}).get_json()["items"]
    assert [i["name"] for i in items] == ["a.jpg", "b.png"]
    assert all(i["thumb"] and i["kind"] == "image" for i in items)


def _name(client, folder):
    job = client.post("/api/name", json={"folder": str(folder)}).get_json()["job"]
    for _ in range(100):
        r = client.get("/api/name/" + job).get_json()
        if r["done"]:
            return r
        time.sleep(0.05)
    raise AssertionError("job never finished")


def test_name_rename_undo(client, folder):
    r = _name(client, folder)
    assert r["results"][str(folder / "a.jpg")]["proposed"] == "Slide 1"
    assert r["results"][str(folder / "b.png")]["proposed"] == "Slide 2"
    items = [{"path": str(folder / "a.jpg"), "new_name": "Slide 1"}, {"path": str(folder / "b.png"), "new_name": "b"}]
    r = client.post("/api/rename", json={"items": items}).get_json()
    assert r["renamed"] == 1 and (folder / "Slide 1.jpg").exists() and (folder / "b.png").exists()
    assert client.post("/api/undo", json={"journal": "../config"}).status_code == 404
    assert client.post("/api/undo", json={"journal": r["journal"]}).get_json()["restored"] == 1
    assert (folder / "a.jpg").exists()
    assert client.post("/api/undo", json={"journal": r["journal"]}).status_code == 404


def test_results_keyed_by_path_survive_a_file_landing_mid_flight(client, folder):
    """A file arriving between scan and name used to shift every result by one,
    so each card showed the right thumbnail beside its neighbour's name."""
    (folder / "0_new.png").write_bytes((folder / "a.jpg").read_bytes())
    r = _name(client, folder)
    # 0_new sorts first, so positional ids would hand a.jpg -> "Slide 2".
    assert r["results"][str(folder / "0_new.png")]["proposed"] == "Slide 1"
    assert r["results"][str(folder / "a.jpg")]["proposed"] == "Slide 2"
    # A card the browser holds but the server no longer sees simply has no entry.
    assert str(folder / "gone.png") not in r["results"]


def test_name_requires_key(client, folder, monkeypatch):
    monkeypatch.delenv("SMART_EXPLORER_MOCK")
    r = client.post("/api/name", json={"folder": str(folder)})
    assert r.status_code == 400 and "Settings" in r.get_json()["error"]


def test_pick_folder_without_window(client):
    assert client.get("/api/pick-folder").get_json() == {"folder": None}
