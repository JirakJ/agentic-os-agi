"""Allowlist / denylist loader with mtime cache. Schema: hooks/scripts/allowlist.json.

Glob semantics are gitignore-style: `**` crosses directory separators, `*`/`?` do NOT
(fnmatch's `*` crossing slashes is a security footgun in both directions - it made
`**/test_*.py` swallow `.../test_x_dir/anything.py`)."""
from __future__ import annotations

import json
import re
from pathlib import Path

_FILE = Path(__file__).resolve().parent.parent / "allowlist.json"
_cache: dict = {"mtime": None, "data": {}, "rx": {}}

def load() -> dict:
    try:
        mtime = _FILE.stat().st_mtime
        if _cache["mtime"] != mtime:
            _cache["data"] = json.loads(_FILE.read_text(encoding="utf-8"))
            _cache["mtime"] = mtime
            _cache["rx"] = {}
    except Exception:
        pass
    return _cache["data"] or {}

def _glob_rx(pat: str) -> re.Pattern:
    rx = _cache["rx"].get(pat)
    if rx is not None:
        return rx
    out: list[str] = []
    i = 0
    while i < len(pat):
        c = pat[i]
        if c == "*":
            if pat[i:i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if pat[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    rx = re.compile("^" + "".join(out) + "$")
    _cache["rx"][pat] = rx
    return rx

def path_matches(path: str, key: str) -> bool:
    p = path.replace("\\", "/").lstrip("/")
    for pat in load().get(key, []):
        if _glob_rx(pat.lstrip("/")).match(p):
            return True
    return False

def regex_hits(text: str, key: str) -> list[str]:
    hits = []
    for pat in load().get(key, []):
        try:
            if re.search(pat, text, re.IGNORECASE | re.MULTILINE):
                hits.append(pat)
        except re.error:
            continue
    return hits
