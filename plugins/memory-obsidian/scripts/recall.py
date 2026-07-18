#!/usr/bin/env python3
"""Query the L4 index. Returns ranked snippets, not documents.

Snippets are the point: a note dumped into context costs thousands of tokens and buries the answer.
A ranked snippet with its path costs tens and tells Claude where to read further if it matters.

Usage:
    recall.py "what did I decide about jq"
    recall.py "hook latency" --limit 8 --layer L2-episodic
    recall.py "release process" --json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from index_vault import default_index_path  # noqa: E402
from vaultdb import Embedder, connect, search  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Hybrid recall over the vault and episodic memory.")
    parser.add_argument("query", help="natural-language query")
    parser.add_argument("--limit", "-n", type=int, default=5)
    parser.add_argument("--layer", choices=["L2-episodic", "L3-knowledge"], default=None)
    parser.add_argument("--index", type=Path, default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    index_path = args.index or default_index_path()
    if not index_path.exists():
        print("recall: no index — run index_vault.py first", file=sys.stderr)
        return 2

    db, has_vec = connect(index_path)
    embedder = Embedder()
    if has_vec and embedder.available:
        embedder.load()
    vector_arm = has_vec and embedder.available

    started = time.perf_counter()
    hits = search(db, args.query, limit=args.limit, has_vec=has_vec,
                  embedder=embedder, layer=args.layer)
    elapsed = (time.perf_counter() - started) * 1000
    db.close()

    if args.as_json:
        print(json.dumps({
            "query": args.query,
            "elapsed_ms": round(elapsed, 1),
            "vector_arm": vector_arm,
            "hits": [
                {"path": h.path, "heading": h.heading, "snippet": h.snippet,
                 "score": round(h.score, 5), "why": h.why}
                for h in hits
            ],
        }, ensure_ascii=False, indent=2))
        return 0 if hits else 1

    if not hits:
        print(f"no hits for {args.query!r} ({elapsed:.0f} ms)")
        return 1

    for i, hit in enumerate(hits, start=1):
        location = f"{hit.path}" + (f" › {hit.heading}" if hit.heading else "")
        print(f"\n{i}. {location}   [{hit.why}]")
        print(f"   {hit.snippet[:300]}{'…' if len(hit.snippet) > 300 else ''}")
    arm = "BM25 + vectors" if vector_arm else "BM25 only"
    print(f"\n{len(hits)} hit(s) in {elapsed:.0f} ms  [{arm}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
