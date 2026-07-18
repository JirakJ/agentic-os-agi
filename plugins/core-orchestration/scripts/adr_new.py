#!/usr/bin/env python3
"""Create and index MADR 4.0.0 decision records.

Allocates the next number, renders the template, and maintains supersession chains on both ends so
the graph never goes one-sided. Never overwrites an existing record.

Usage:
    adr_new.py "Use model2vec for local embeddings"
    adr_new.py "Replace model2vec with MLX" --supersedes 0007
    adr_new.py "Gate Stop on dirty core logic" --status accepted --affects hook/commit-adr-gate
    adr_new.py --list
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

SLUG_STRIP = re.compile(r"[^a-z0-9]+")
ADR_FILE = re.compile(r"^(\d{4})-(.+)\.md$")
FM_FIELD = re.compile(r"^(\w[\w-]*):\s*(.*)$")

TEMPLATE = """---
status: {status}
date: {date}
decision-makers: [{decision_makers}]
consulted: []
informed: []
affects: [{affects}]
supersedes: [{supersedes}]
superseded-by: []
---

# ADR-{number} — {title}

## Context and Problem Statement

<!-- Two to four sentences. What is true about the world that makes this a decision rather than an
     obvious call. Assume the reader has forgotten the session that produced it. -->

## Decision Drivers

<!-- Only drivers that actually rule an option out. Numbers where numbers exist. -->

*

## Considered Options

<!-- At least two, honestly. One option means this is a changelog entry, not a decision. -->

*
*

## Decision Outcome

Chosen option: "", because <the one sentence that does the work>.

### Consequences

* Good, because
* Bad, because <the cost being accepted — this half earns the record its keep>

### Confirmation

<!-- How you would find out this was wrong. A threshold, a benchmark, an error rate. -->

## Pros and Cons of the Options

### <option 1>

* Good, because
* Neutral, because
* Bad, because

### <option 2>

* Good, because
* Neutral, because
* Bad, because

## More Information

<!-- Prior art, benchmarks, the commit that implements this, when to revisit. -->
"""


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    print("adr_new: not inside a marketplace (no .claude-plugin/marketplace.json)", file=sys.stderr)
    sys.exit(2)


def slugify(title: str) -> str:
    slug = SLUG_STRIP.sub("-", title.lower()).strip("-")
    if not slug:
        print("adr_new: title produces an empty slug", file=sys.stderr)
        sys.exit(2)
    return slug


def existing(adr_dir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(adr_dir.glob("*.md")):
        match = ADR_FILE.match(path.name)
        if match:
            found[match.group(1)] = path
    return found


def next_number(records: dict[str, Path]) -> str:
    return f"{max((int(n) for n in records), default=0) + 1:04d}"


def read_field(path: Path, field: str) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    for line in text[3:end].splitlines():
        match = FM_FIELD.match(line.strip())
        if match and match.group(1) == field:
            return match.group(2).strip()
    return None


def set_field(path: Path, field: str, value: str) -> None:
    """Rewrite one frontmatter field in place, leaving the body byte-identical."""
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    if not text.startswith("---") or end == -1:
        print(f"adr_new: {path.name} has no usable frontmatter", file=sys.stderr)
        sys.exit(1)

    head, body = text[3:end], text[end:]
    out, replaced = [], False
    for line in head.splitlines():
        match = FM_FIELD.match(line.strip())
        if match and match.group(1) == field:
            out.append(f"{field}: {value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{field}: {value}")
    path.write_text("---" + "\n".join(out) + body, encoding="utf-8")


def merge_list(current: str | None, addition: str) -> str:
    items = []
    if current:
        inner = current.strip()
        if inner.startswith("[") and inner.endswith("]"):
            inner = inner[1:-1]
        items = [v.strip() for v in inner.split(",") if v.strip()]
    if addition not in items:
        items.append(addition)
    return "[" + ", ".join(items) + "]"


def cmd_list(adr_dir: Path) -> int:
    records = existing(adr_dir)
    if not records:
        print("no decision records yet")
        return 0

    rows = []
    for number, path in sorted(records.items()):
        status = read_field(path, "status") or "?"
        date = read_field(path, "date") or ""
        title = ADR_FILE.match(path.name).group(2).replace("-", " ")
        rows.append((number, status, date, title))

    width = max(len(r[1]) for r in rows)
    for number, status, date, title in rows:
        marker = {"accepted": "✓", "proposed": "·", "superseded": "×", "deprecated": "×"}.get(status, "?")
        print(f"{marker} ADR-{number}  {status.ljust(width)}  {date}  {title}")

    open_count = sum(1 for r in rows if r[1] == "proposed")
    if open_count:
        print(f"\n{open_count} proposed record(s) — accept them or delete them")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a MADR 4.0.0 decision record.")
    parser.add_argument("title", nargs="?", help="short present-tense title naming the decision")
    parser.add_argument("--supersedes", metavar="NNNN", help="number of the record this replaces")
    parser.add_argument("--status", default="proposed",
                        choices=["proposed", "accepted", "deprecated", "superseded"])
    parser.add_argument("--affects", default="", help="comma-separated component ids, e.g. skill/vault-recall")
    parser.add_argument("--decision-makers", default="Jakub Jirak")
    parser.add_argument("--list", action="store_true", dest="do_list", help="index existing records")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve() if args.root else repo_root()
    adr_dir = root / "adr"
    adr_dir.mkdir(exist_ok=True)

    if args.do_list:
        return cmd_list(adr_dir)

    if not args.title:
        parser.error("a title is required (or use --list)")

    records = existing(adr_dir)
    number = next_number(records)
    path = adr_dir / f"{number}-{slugify(args.title)}.md"

    if path.exists():  # unreachable via next_number, but never clobber a record
        print(f"adr_new: refusing to overwrite {path.name}", file=sys.stderr)
        return 1

    supersedes = ""
    if args.supersedes:
        target = args.supersedes.zfill(4)
        if target not in records:
            print(f"adr_new: ADR-{target} does not exist", file=sys.stderr)
            return 1
        supersedes = target

    affects = ", ".join(a.strip() for a in args.affects.split(",") if a.strip())

    path.write_text(
        TEMPLATE.format(
            number=number,
            title=args.title,
            status=args.status,
            date=dt.date.today().isoformat(),
            decision_makers=args.decision_makers,
            affects=affects,
            supersedes=supersedes,
        ),
        encoding="utf-8",
    )

    if supersedes:
        old = records[supersedes]
        set_field(old, "status", "superseded")
        set_field(old, "superseded-by", merge_list(read_field(old, "superseded-by"), number))
        set_field(old, "date", dt.date.today().isoformat())
        print(f"ADR-{supersedes} → superseded by ADR-{number}: {old.relative_to(root)}")

    print(path.relative_to(root))
    if supersedes:
        print(f"\nBoth records commit together — supersession is one logical fact:\n"
              f"  git add adr/{path.name} adr/{records[supersedes].name}\n"
              f"  git commit -m 'docs(adr): add ADR-{number} superseding ADR-{supersedes}'")
    else:
        print(f"\nCommit the record before the code it justifies:\n"
              f"  git add adr/{path.name}\n"
              f"  git commit -m 'docs(adr): add ADR-{number} on {args.title.lower()}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
