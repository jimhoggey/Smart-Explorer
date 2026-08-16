import io
import json
from urllib.error import HTTPError, URLError

import pytest

import namer


def stub(monkeypatch, content, seen=None):
    body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    def fake(req, timeout=None):
        if seen is not None:
            seen.append(req)
        return io.BytesIO(body)

    monkeypatch.setattr(namer, "urlopen", fake)


def raise_(exc):
    def fake(req, timeout=None):
        raise exc

    return fake


def test_parse_json_fenced_and_prefixed():
    assert namer.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert namer.parse_json('Sure! ["x", "y"] done') == ["x", "y"]
    assert namer.parse_json('Names {see below}: ["A", "B"]') == ["A", "B"]
    with pytest.raises(namer.NamerError):
        namer.parse_json("no json here")


def test_chat_http_error(monkeypatch):
    err = HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b'{"error":"bad key"}'))
    monkeypatch.setattr(namer, "urlopen", raise_(err))
    with pytest.raises(namer.NamerError, match="401"):
        namer.chat("k", "m", [])


def test_describe(monkeypatch):
    seen = []
    stub(monkeypatch, '{"kind": "Giving", "headline": "Give", "details": "", "has_details": false}', seen)
    d = namer.describe("k", "m", {"id": 1, "name": "a.png"}, ["abc"])
    assert d["kind"] == "Giving"
    assert seen[0].get_header("Authorization") == "Bearer k"
    assert b"data:image/jpeg;base64,abc" in seen[0].data


def test_describe_error(monkeypatch):
    monkeypatch.setattr(namer, "urlopen", raise_(URLError("down")))
    d = namer.describe("k", "m", {"id": 1, "name": "a.png"}, ["abc"])
    assert "error" in d and "down" in d["error"]


DESCS = [
    {"index": 0, "original": "a.png", "headline": "Giving"},
    {"index": 1, "original": "b.png", "headline": "Giving"},
    {"index": 2, "original": "c.png", "headline": ""},
]


def test_name_all(monkeypatch):
    stub(monkeypatch, '["A", "B", "C"]')
    assert namer.name_all("k", "m", DESCS) == ["A", "B", "C"]


def test_name_all_tolerates_wrapped_shapes(monkeypatch):
    stub(monkeypatch, '{"names": [{"index": 0, "name": "A"}, "B", "C"]}')
    assert namer.name_all("k", "m", DESCS) == ["A", "B", "C"]
    stub(monkeypatch, '["A", "B"]')
    assert namer.name_all("k", "m", DESCS) == ["Giving", "Giving (2)", "c"]


def test_name_all_fallback(monkeypatch):
    monkeypatch.setattr(namer, "urlopen", raise_(URLError("down")))
    assert namer.name_all("k", "m", DESCS) == ["Giving", "Giving (2)", "c"]


def test_run(monkeypatch):
    def chat(key, model, messages, timeout=90):
        if isinstance(messages[1]["content"], list):
            return '{"kind": "Giving", "headline": "Give", "details": "", "has_details": false}'
        return json.dumps(["Name %d" % d["index"] for d in json.loads(messages[1]["content"])])

    monkeypatch.setattr(namer, "chat", chat)
    items = [{"id": i, "path": "/x/%d.png" % i, "name": "%d.png" % i, "kind": "image"} for i in range(3)]

    def encode(item):
        if item["id"] == 1:
            raise OSError("bad file")
        return ["img"]

    calls = []
    out = namer.run("k", "m", items, encode, on_progress=lambda *a: calls.append(a))
    assert [r["proposed"] for r in out] == ["Name 0", "1", "Name 2"]
    assert "error" in out[1] and "error" not in out[0]
    assert {c[0] for c in calls if c[1] == "named"} == {0, 1, 2}


def test_mock_run():
    items = [{"id": 7, "name": "a.png"}, {"id": 8, "name": "b.png"}]
    calls = []
    out = namer.mock_run(items, on_progress=lambda *a: calls.append(a))
    assert out == [{"id": 7, "proposed": "Slide 1"}, {"id": 8, "proposed": "Slide 2"}]
    assert len(calls) == 2


def test_check_key(monkeypatch):
    monkeypatch.setattr(namer, "urlopen", lambda req, timeout=None: io.BytesIO(b'{"data": {"label": "sk-1"}}'))
    assert namer.check_key("k") == {"ok": True, "label": "sk-1"}
    monkeypatch.setattr(namer, "urlopen", raise_(URLError("down")))
    assert namer.check_key("k")["ok"] is False
