import json
from pathlib import Path

import config
import renamer
import scanner


def test_scan(tmp_path):
    for n in ["b.PNG", "a.mp4", "c.txt"]:
        (tmp_path / n).write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.png").write_bytes(b"x")
    items = scanner.scan(str(tmp_path))
    assert [(i["name"], i["kind"], i["id"]) for i in items] == [("a.mp4", "video", 0), ("b.PNG", "image", 1)]
    assert items[0]["path"] == str(tmp_path / "a.mp4")


def test_config_roundtrip_and_corrupt(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "cfg")
    assert config.load() == {}
    assert config.save(key="k") == {"key": "k"}
    assert config.load()["key"] == "k"
    assert config.save(model="m") == {"key": "k", "model": "m"}
    (tmp_path / "cfg" / "config.json").write_text("{not json")
    assert config.load() == {}


def test_sanitize():
    assert renamer.sanitize("Giving: Full/Details?", ".png") == "Giving Full Details.png"
    assert renamer.sanitize("  \x01 ", ".png") == "Untitled.png"
    assert renamer.sanitize("a" * 200, ".png") == "a" * 100 + ".png"
    assert renamer.sanitize("con", ".png") == "_con.png"
    assert renamer.sanitize("Aux. Details", ".png") == "_Aux. Details.png"


def test_plan_collisions_and_unchanged(tmp_path):
    (tmp_path / "Giving.png").write_bytes(b"x")
    for n in ["one.png", "two.png", "same.png"]:
        (tmp_path / n).write_bytes(b"x")
    items = [
        {"path": str(tmp_path / "one.png"), "new_name": "Giving"},
        {"path": str(tmp_path / "two.png"), "new_name": "Giving"},
        {"path": str(tmp_path / "same.png"), "new_name": "same"},
    ]
    assert renamer.plan(items) == [
        (str(tmp_path / "one.png"), str(tmp_path / "Giving (2).png")),
        (str(tmp_path / "two.png"), str(tmp_path / "Giving (3).png")),
    ]


def test_apply_and_undo(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    journal = tmp_path / "journal"
    pairs = [(str(a), str(tmp_path / "x.png")), (str(b), str(tmp_path / "y.png"))]
    jid = renamer.apply(pairs, journal)["journal"]
    assert not a.exists() and (tmp_path / "x.png").read_bytes() == b"a"
    assert json.loads((journal / (jid + ".json")).read_text()) == [list(p) for p in pairs]
    assert renamer.undo(jid, journal) == 2
    assert a.read_bytes() == b"a" and b.read_bytes() == b"b"
    assert not (journal / (jid + ".json")).exists()


def test_apply_partial_failure_is_journaled(tmp_path):
    a = tmp_path / "a.png"
    a.write_bytes(b"a")
    pairs = [(str(a), str(tmp_path / "x.png")), (str(tmp_path / "missing.png"), str(tmp_path / "y.png"))]
    r = renamer.apply(pairs, tmp_path / "journal")
    assert r["renamed"] == 1 and "missing.png" in r["error"]
    assert renamer.undo(r["journal"], tmp_path / "journal") == 1 and a.exists()


def test_plan_skips_missing_files(tmp_path):
    assert renamer.plan([{"path": str(tmp_path / "nope.png"), "new_name": "x"}]) == []
