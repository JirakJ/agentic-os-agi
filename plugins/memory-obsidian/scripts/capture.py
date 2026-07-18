#!/usr/bin/env python3
"""Write a note into the Obsidian vault (L3) or episodic memory (L2).

Two transports, tried in order (ADR-0004):

  REST  — the Local REST API plugin on 127.0.0.1:27124. Preferred: Obsidian stays authoritative
          over its own index, so a note written while the app is open is immediately linkable and
          searchable rather than appearing after the next rescan.
  FS    — direct file write. Fallback for when Obsidian is closed or the plugin is off. Correct,
          just invisible to Obsidian's index until it notices the file.

Auth for REST comes from $OBSIDIAN_API_KEY. Nothing is read from disk to find it and it is never
logged — the secret guard would refuse to read a file holding it anyway, which is the point.

Usage:
    capture.py --title "Session: hook latency" --body "..." --folder 10-Inbox/agent-capture
    capture.py --title "Fact" --body "..." --tags agent,decision --append
    echo "..." | capture.py --title "From stdin"
    capture.py --check          # which transport is live
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

REST_BASE = os.environ.get("OBSIDIAN_REST_URL", "https://127.0.0.1:27124")
SLUG_STRIP = re.compile(r"[^a-z0-9]+")
UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def slugify(title: str) -> str:
    return SLUG_STRIP.sub("-", title.lower()).strip("-")[:80] or "note"


def safe_name(title: str) -> str:
    """Obsidian tolerates most characters; the filesystem does not."""
    return UNSAFE.sub("-", title).strip(". ")[:100] or "note"


def rest_context() -> ssl.SSLContext:
    """The plugin ships a self-signed cert for 127.0.0.1. Verifying it would mean pinning a cert
    that regenerates; the connection cannot leave the loopback interface regardless."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def rest_call(method: str, path: str, body: bytes | None = None,
              content_type: str = "text/markdown", timeout: float = 5.0):
    key = os.environ.get("OBSIDIAN_API_KEY")
    if not key:
        return None, "OBSIDIAN_API_KEY is not set"
    url = f"{REST_BASE.rstrip('/')}/{path.lstrip('/')}"
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Authorization", f"Bearer {key}")
    if body is not None:
        request.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=rest_context()) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, ssl.SSLError, OSError) as exc:
        return None, str(exc)


def rest_alive() -> bool:
    status, _ = rest_call("GET", "/")
    return status is not None and 200 <= status < 500


def render(title: str, body: str, tags: list[str], source: str) -> str:
    today = dt.datetime.now().astimezone()
    front = [
        "---",
        f"title: {title}",
        f"created: {today.isoformat(timespec='seconds')}",
        f"source: {source}",
    ]
    if tags:
        front.append(f"tags: [{', '.join(tags)}]")
    front.append("---")
    return "\n".join(front) + f"\n\n# {title}\n\n{body.strip()}\n"


def vault_root(explicit: str | None) -> Path | None:
    raw = explicit or os.environ.get("AGENTIC_OS_VAULT")
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if path.is_dir() else None


def write_fs(root: Path, rel: str, content: str, append: bool) -> Path:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if append and target.is_file():
        with target.open("a", encoding="utf-8") as handle:
            handle.write("\n\n" + content.split("---", 2)[-1].lstrip())
    else:
        target.write_text(content, encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a note into the vault or episodic memory.")
    parser.add_argument("--title", help="note title")
    parser.add_argument("--body", help="note body (or pipe on stdin)")
    parser.add_argument("--folder", default=None, help="vault-relative folder (or $AGENTIC_OS_CAPTURE_FOLDER)")
    parser.add_argument("--tags", default="", help="comma-separated")
    parser.add_argument("--source", default="claude-code", help="provenance recorded in frontmatter")
    parser.add_argument("--vault", help="vault root (or $AGENTIC_OS_VAULT)")
    parser.add_argument("--append", action="store_true", help="append if the note exists")
    parser.add_argument("--transport", choices=["auto", "rest", "fs"], default="auto")
    parser.add_argument("--check", action="store_true", help="report which transport is live")
    args = parser.parse_args()

    if args.check:
        root = vault_root(args.vault)
        rest = rest_alive()
        print(f"REST  {REST_BASE}  {'live' if rest else 'unreachable'}"
              + ("" if os.environ.get("OBSIDIAN_API_KEY") else "  (OBSIDIAN_API_KEY unset)"))
        print(f"FS    {root or '—'}  {'ok' if root else 'AGENTIC_OS_VAULT unset or not a directory'}")
        if rest:
            print("\ntransport: rest — Obsidian's index stays authoritative")
        elif root:
            print("\ntransport: fs — Obsidian will not see the note until it rescans")
        else:
            print("\ntransport: none — capture would fail")
        return 0 if (rest or root) else 1

    if not args.title:
        parser.error("--title is required")

    body = args.body if args.body is not None else sys.stdin.read()
    if not body.strip():
        print("capture: empty body", file=sys.stderr)
        return 2

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    folder = (args.folder or os.environ.get("AGENTIC_OS_CAPTURE_FOLDER") or "10-Inbox/agent-capture").strip("/")
    stamp = dt.date.today().isoformat()
    rel = f"{folder}/{stamp}-{slugify(args.title)}.md"
    content = render(args.title, body, tags, args.source)

    if args.transport in ("auto", "rest"):
        method = "POST" if args.append else "PUT"
        status, detail = rest_call(method, f"/vault/{rel}", content.encode("utf-8"))
        if status is not None and 200 <= status < 300:
            print(f"captured (rest): {rel}")
            return 0
        if args.transport == "rest":
            print(f"capture: REST failed — {status or ''} {detail}", file=sys.stderr)
            return 1

    root = vault_root(args.vault)
    if root is None:
        print("capture: no transport available — set OBSIDIAN_API_KEY for REST, or "
              "AGENTIC_OS_VAULT for a direct write. `capture.py --check` explains which is missing.",
              file=sys.stderr)
        return 1

    target = write_fs(root, rel, content, args.append)
    print(f"captured (fs): {target.relative_to(root)}")
    print("  Obsidian will not index this until it rescans; start the Local REST API plugin to "
          "keep the index live")
    return 0


if __name__ == "__main__":
    sys.exit(main())
