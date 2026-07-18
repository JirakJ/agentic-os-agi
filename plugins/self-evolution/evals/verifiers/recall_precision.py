#!/usr/bin/env python3
"""Capability verifier: hybrid recall ranks the answering note first and is empty on no-match.

Indexes a fixture vault, runs queries, asserts the right note tops the results and a genuine
no-match returns nothing on the BM25 path (the deterministic mode). Prints one JSON line.
"""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path


def find_root() -> Path:
    for c in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
        if (c / ".claude-plugin" / "marketplace.json").is_file():
            return c
    raise SystemExit(json.dumps({"pass": False, "score": 0.0, "detail": "root not found"}))


def main() -> int:
    root = find_root()
    scripts = root / "plugins" / "memory-obsidian" / "scripts"
    if not (scripts / "vaultdb.py").is_file():
        print(json.dumps({"pass": False, "score": 0.0, "detail": "vaultdb.py missing"})); return 0
    sys.path.insert(0, str(scripts))
    from vaultdb import connect, init_schema, index_file, search  # type: ignore

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        vault = tmp / "v"; (vault / "n").mkdir(parents=True)
        (vault / "n" / "router.md").write_text(
            "---\ntitle: Cascade Router\n---\n# Cascade Router\n"
            "Four-tier model selection cutting token cost by 94 percent.\n\n"
            "## Escalation\nTier 1 classifies. Tier 4 reasons. The 2-to-3 gate holds the savings.\n")
        (vault / "n" / "metrics.md").write_text(
            "---\ntitle: Metrics Platform\n---\n# Metrics Platform\n"
            "TimescaleDB hypertables with a 90-day compression policy.\n")
        (vault / "n" / "obsidian.md").write_text(
            "---\ntitle: Obsidian Vault\n---\n# Obsidian Vault\n"
            "The knowledge base is a separate git repository, versioned by Obsidian Git.\n")

        db, has_vec = connect(tmp / "i.db")
        init_schema(db, has_vec)
        # BM25-only path (deterministic across environments): the eval must not depend on a model.
        for p in sorted(vault.rglob("*.md")):
            index_file(db, vault, p, "L3-knowledge", None, False)
        db.commit()

        def top(q):
            hits = search(db, q, limit=3, has_vec=False, embedder=None)
            return hits[0].path if hits else None

        checks = {
            "token cost → router": top("token cost tier escalation") == "n/router.md",
            "compression → metrics": top("hypertable compression policy") == "n/metrics.md",
            "separate repo → obsidian": top("separate git repository versioned") == "n/obsidian.md",
            "no-match is empty": search(db, "kubernetes helm istio nomad", limit=3,
                                        has_vec=False, embedder=None) == [],
        }
        passed, total = sum(checks.values()), len(checks)
        failed = [k for k, v in checks.items() if not v]
        print(json.dumps({"pass": passed == total, "score": round(passed / total, 4),
                          "detail": "" if passed == total else "failed: " + ", ".join(failed)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
