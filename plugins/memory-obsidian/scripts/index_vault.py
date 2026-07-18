#!/usr/bin/env python3
"""Build or refresh the L4 retrieval index over the vault (L3) and episodic memory (L2).

Incremental by default: a file is re-read only when its mtime moved and its content hash actually
changed. The index is derived data (ADR-0003) — deleting it loses nothing.

Usage:
    index_vault.py                       # incremental
    index_vault.py --rebuild             # drop and rebuild from scratch
    index_vault.py --stats               # what is in there
    index_vault.py --vault ~/Documents/Vault --memory ./memory
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vaultdb import Embedder, connect, index_file, init_schema, needs_reindex, prune_missing, stats  # noqa: E402

SKIP_DIRS = {".git", ".obsidian", ".trash", ".index", "node_modules", "__pycache__", ".DS_Store"}


def default_index_path() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_DATA")
    base = Path(raw) if raw else Path.home() / ".claude" / "plugins" / "data" / "memory-obsidian"
    base.mkdir(parents=True, exist_ok=True)
    return base / "index.db"


def resolve_vault(explicit: str | None) -> Path | None:
    raw = explicit or os.environ.get("AGENTIC_OS_VAULT")
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if path.is_dir() else None


def walk(root: Path):
    for path in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the L4 retrieval index.")
    parser.add_argument("--vault", help="Obsidian vault root (or $AGENTIC_OS_VAULT)")
    parser.add_argument("--memory", help="episodic memory dir (default: <repo>/memory)")
    parser.add_argument("--index", type=Path, default=None, help="index path (default: plugin data dir)")
    parser.add_argument("--rebuild", action="store_true", help="drop and rebuild")
    parser.add_argument("--stats", action="store_true", dest="show_stats")
    parser.add_argument("--quiet", "-q", action="store_true")
    args = parser.parse_args()

    index_path = args.index or default_index_path()

    if args.rebuild and index_path.exists():
        index_path.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = index_path.with_name(index_path.name + suffix)
            if sidecar.exists():
                sidecar.unlink()

    db, has_vec = connect(index_path)
    init_schema(db, has_vec)

    if args.show_stats:
        info = stats(db, has_vec)
        print(f"index    {index_path}")
        print(f"docs     {info['docs']}  ({', '.join(f'{k}: {v}' for k, v in info['by_layer'].items()) or 'empty'})")
        print(f"chunks   {info['chunks']}")
        print(f"vectors  {info['vectors']}" + ("" if info["vector_arm"] else "   (vector arm off — sqlite-vec not loadable)"))
        return 0

    roots: dict[str, Path] = {}
    vault = resolve_vault(args.vault)
    if vault:
        roots["L3-knowledge"] = vault
    memory = Path(args.memory).expanduser().resolve() if args.memory else None
    if memory and memory.is_dir():
        roots["L2-episodic"] = memory

    if not roots:
        print("index_vault: nothing to index — pass --vault/--memory or set $AGENTIC_OS_VAULT",
              file=sys.stderr)
        return 2

    embedder = Embedder()
    if has_vec and embedder.available:
        embedder.load()
    vector_arm = has_vec and embedder.available
    if not vector_arm and not args.quiet:
        why = "sqlite-vec extension not loadable — pip install sqlite-vec" if not has_vec else embedder.reason
        print(f"  vector arm off: {why}")
        print("  BM25 recall is unaffected (ADR-0007)")

    started = time.perf_counter()
    indexed = skipped = chunks = 0

    for layer, root in roots.items():
        for path in walk(root):
            rel = str(path.relative_to(root))
            if not args.rebuild and not needs_reindex(db, rel, path):
                skipped += 1
                continue
            chunks += index_file(db, root, path, layer, embedder, vector_arm)
            indexed += 1
            if not args.quiet and indexed % 50 == 0:
                print(f"  {indexed} indexed…")

    removed = prune_missing(db, roots, has_vec)
    db.commit()
    db.execute("PRAGMA optimize")
    db.close()

    if not args.quiet:
        elapsed = (time.perf_counter() - started) * 1000
        arm = "BM25 + vectors" if vector_arm else "BM25 only"
        print(f"index: {indexed} indexed, {skipped} unchanged, {removed} pruned, "
              f"{chunks} chunks in {elapsed:.0f} ms  [{arm}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
