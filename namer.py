import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
KEY_URL = "https://openrouter.ai/api/v1/key"
HEADERS = {"Content-Type": "application/json", "HTTP-Referer": "https://smart-explorer.local", "X-Title": "Smart Explorer"}
DESCRIBE_PROMPT = 'You describe church presentation slides. Reply ONLY with JSON: {"kind": short category like Giving, Announcement, Sermon Title, Worship Lyrics, Countdown, Welcome, Background; "headline": the main visible text; "details": other visible text/details in one line, or ""; "has_details": true/false}'
NAME_PROMPT = 'You name slide files from their descriptions. Reply ONLY with a JSON array of strings, one per input, same order. Rules: short Title Case name based on content, like "Giving - Full Details" or "Sermon Title - Anchored Week 3". When several inputs share a kind, distinguish them by what differs (details vs title only, different text, etc.). Never repeat a name. No file extensions, no numbering unless it is on the slide.'


class NamerError(Exception):
    pass


def _request(url, key, data=None, timeout=90, tries=3):
    req = Request(url, data=data, headers={**HEADERS, "Authorization": "Bearer " + key})
    for attempt in range(tries):
        last = attempt == tries - 1
        try:
            with urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except HTTPError as e:
            if last or not (e.code == 429 or e.code >= 500):
                raise NamerError("OpenRouter returned HTTP %s: %s" % (e.code, e.read().decode(errors="replace")[:200]))
        except OSError as e:
            if last:
                raise NamerError("Could not reach OpenRouter: %s" % e)
        except ValueError:
            raise NamerError("OpenRouter returned invalid JSON")
        time.sleep(2 ** attempt)


def chat(key, model, messages, timeout=90):
    data = _request(ENDPOINT, key, json.dumps({"model": model, "messages": messages}).encode(), timeout)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise NamerError("Unexpected reply from OpenRouter: %s" % json.dumps(data)[:200])


def parse_json(text):
    for m in re.finditer(r"[\[{]", text):
        try:
            return json.JSONDecoder().raw_decode(text, m.start())[0]
        except ValueError:
            pass
    raise NamerError("Model reply was not JSON: %s" % text[:100])


def describe(key, model, item, images):
    content = [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b}} for b in images]
    content.append({"type": "text", "text": "Describe this slide."})
    try:
        d = parse_json(chat(key, model, [{"role": "system", "content": DESCRIBE_PROMPT}, {"role": "user", "content": content}]))
        return d if isinstance(d, dict) else {"error": "Model reply was not an object"}
    except Exception as e:
        return {"error": str(e)}


def _dedupe(names):
    seen, out = set(), []
    for n in names:
        c, i = n, 2
        while c.lower() in seen:
            c, i = "%s (%d)" % (n, i), i + 1
        seen.add(c.lower())
        out.append(c)
    return out


def name_all(key, model, descs):
    """Return (names, error). On failure names fall back to raw slide text and
    error explains why — the caller MUST surface it, or the batch looks fine."""
    err = None
    try:
        names = parse_json(chat(key, model, [{"role": "system", "content": NAME_PROMPT}, {"role": "user", "content": json.dumps(descs)}]))
        if isinstance(names, dict):
            names = next((v for v in names.values() if isinstance(v, list)), None)
        if not isinstance(names, list) or len(names) != len(descs):
            raise NamerError("expected %d names, got %s" % (len(descs), len(names) if isinstance(names, list) else type(names).__name__))
        names = [n.get("name") if isinstance(n, dict) else n for n in names]
    except Exception as e:
        names = [None] * len(descs)
        err = "AI naming failed (%s) — these are the raw words on each slide, not chosen names." % e
    fallback = lambda d: d.get("headline") or Path(d["original"]).stem
    return _dedupe(n.strip() if isinstance(n, str) and n.strip() else fallback(d) for n, d in zip(names, descs)), err


def run(key, model, items, encode, on_progress=None):
    notify = on_progress or (lambda *a: None)

    def step(item):
        try:
            d = describe(key, model, item, encode(item))
        except Exception as e:
            d = {"error": "Could not read file: %s" % e}
        notify(item["id"], "described")
        return d

    with ThreadPoolExecutor(5) as ex:
        descs = list(ex.map(step, items))
    ok = [{**d, "index": i, "original": it["name"]} for i, (it, d) in enumerate(zip(items, descs)) if "error" not in d]
    names, name_err = name_all(key, model, ok) if ok else ([], None)
    proposed = dict(zip((d["index"] for d in ok), names))
    out = []
    for i, (it, d) in enumerate(zip(items, descs)):
        r = {"id": it["id"], "path": it["path"], "proposed": proposed.get(i, Path(it["name"]).stem)}
        if "error" in d:
            r["error"] = d["error"]
        elif name_err:
            r["error"] = name_err
        notify(it["id"], "named", r["proposed"])
        out.append(r)
    return out


def check_key(key):
    try:
        return {"ok": True, "label": (_request(KEY_URL, key).get("data") or {}).get("label")}
    except NamerError as e:
        return {"ok": False, "error": str(e)}


def mock_run(items, on_progress=None):
    out = []
    for i, it in enumerate(items, 1):
        r = {"id": it["id"], "path": it["path"], "proposed": "Slide %d" % i}
        if on_progress:
            on_progress(it["id"], "named", r["proposed"])
        out.append(r)
    return out
