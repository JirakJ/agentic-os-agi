#!/usr/bin/env python3
"""L4 retrieval index: SQLite FTS5 with an optional sqlite-vec rerank, fused by RRF.

The index is a cache in the strict sense (ADR-0003): content-addressed by file hash, invalidated by
mtime, rebuildable from the vault and the episodic memory dir with one command. Nothing lives here
that does not live somewhere else first.

Two arms (ADR-0007):
  BM25 (FTS5)        — always available, stdlib sqlite3 only. Strong on proper nouns, ADR ids,
                       tool names: the majority of real queries against a personal vault.
  vectors (sqlite-vec) — optional. Answers queries that share no vocabulary with their target.
                       Absent → recall still works, just lexically.

Reciprocal Rank Fusion merges them without score calibration, which is what lets the vector arm
appear or vanish between runs without retuning anything.

Import as a module; index_vault.py and recall.py are the entry points.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1
EMBED_MODEL = os.environ.get("AGENTIC_OS_EMBED_MODEL", "minishlab/potion-base-8M")
EMBED_DIM = 256
RRF_K = 60  # standard damping; larger flattens rank influence

# Vector arm distance ceiling. Embeddings are L2-normalised at storage and query time, so cosine
# distance maps to L2 as d² = 2(1 - cos): identical → 0, orthogonal → √2 ≈ 1.414. KNN has no
# inherent floor, so without this a nonsense query still returns its k nearest neighbours and the
# arm hallucinates matches — the "confidently wrong" failure ADR-0007 names. The default sits just
# under orthogonal: drop the unrelated, keep anything with real semantic overlap.
VEC_MAX_DISTANCE = float(os.environ.get("AGENTIC_OS_VEC_MAX_DISTANCE", "1.40"))

FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]+\)")
CODE_FENCE = re.compile(r"```.*?```", re.S)
HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.M)
TAG = re.compile(r"(?:^|\s)#([a-zA-Z][\w/-]*)")
FTS_SPECIAL = re.compile(r'["\'()*:^-]')


@dataclass(frozen=True)
class Chunk:
    doc_path: str
    heading: str
    ordinal: int
    text: str


@dataclass(frozen=True)
class Hit:
    path: str
    heading: str
    snippet: str
    score: float
    bm25_rank: int | None
    vec_rank: int | None

    @property
    def why(self) -> str:
        if self.bm25_rank and self.vec_rank:
            return f"keyword #{self.bm25_rank} + semantic #{self.vec_rank}"
        if self.bm25_rank:
            return f"keyword #{self.bm25_rank}"
        return f"semantic #{self.vec_rank}"


class Embedder:
    """model2vec static embeddings. Pure NumPy inference, no torch (ADR-0007).

    Loaded lazily and fails soft: a machine with no model still gets a fully working BM25 index
    (ADR-0007). `reason` distinguishes the three failure modes so the operator is told the truth
    rather than "install the thing you already installed".
    """

    def __init__(self) -> None:
        self._model = None
        self._tried = False
        self.available = False
        self.reason = ""
        try:
            from model2vec import StaticModel  # noqa: F401
            self.available = True
        except ImportError:
            self.reason = "model2vec not installed — pip install model2vec"

    def load(self) -> bool:
        """Idempotent, and silent after the first failure. Called on every recall; a model that
        could not be fetched once will not be fetchable a millisecond later."""
        if self._model is not None:
            return True
        if self._tried or not self.available:
            return False
        self._tried = True
        try:
            from model2vec import StaticModel
            self._model = StaticModel.from_pretrained(EMBED_MODEL)
            return True
        except Exception as exc:
            head = str(exc).strip().splitlines()[0][:120]
            self.reason = f"model '{EMBED_MODEL}' unavailable ({head})"
            self.available = False
            return False

    def encode(self, texts: list[str]):
        if not self.load():
            return None
        return self._model.encode(texts, max_length=512)


def l2_normalize(vectors):
    """Row-wise L2 normalisation. Makes the stored distance metric interpretable and
    backend-independent — the VEC_MAX_DISTANCE threshold only means something for unit vectors.
    A vector that is already unit-length is unchanged; a zero vector is left as-is."""
    import numpy as np

    array = np.asarray(vectors, dtype=np.float32)
    if array.ndim == 1:
        array = array[None, :]
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return array / norms


def vec_available(db: sqlite3.Connection) -> bool:
    try:
        import sqlite_vec
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        return True
    except Exception:
        return False


def connect(index_path: Path) -> tuple[sqlite3.Connection, bool]:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(index_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    has_vec = vec_available(db)
    return db, has_vec


def init_schema(db: sqlite3.Connection, has_vec: bool) -> None:
    db.executescript(f"""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS docs (
            path      TEXT PRIMARY KEY,
            layer     TEXT NOT NULL,
            title     TEXT,
            tags      TEXT,
            links     TEXT,
            mtime     REAL NOT NULL,
            hash      TEXT NOT NULL,
            indexed   REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id       INTEGER PRIMARY KEY,
            path     TEXT NOT NULL REFERENCES docs(path) ON DELETE CASCADE,
            heading  TEXT,
            ordinal  INTEGER NOT NULL,
            text     TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS chunks_path ON chunks(path);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            text,
            heading,
            path UNINDEXED,
            content='chunks',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        );
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, text, heading, path)
            VALUES (new.id, new.text, new.heading, new.path);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text, heading, path)
            VALUES ('delete', old.id, old.text, old.heading, old.path);
        END;
    """)
    if has_vec:
        db.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0("
            f"chunk_id INTEGER PRIMARY KEY, embedding FLOAT[{EMBED_DIM}])"
        )
    db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
               (str(SCHEMA_VERSION),))
    db.commit()


def strip_frontmatter(text: str) -> tuple[str, dict]:
    match = FRONTMATTER.match(text)
    if not match:
        return text, {}
    fm: dict = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith((" ", "\t", "#")):
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip("[]'\"")
    return text[match.end():], fm


def chunk_document(path: str, text: str, max_chars: int = 1200) -> list[Chunk]:
    """Split on headings, then on size. Headings are the author's own semantic boundaries —
    respecting them beats any fixed window."""
    body, _ = strip_frontmatter(text)
    body = CODE_FENCE.sub(" ", body)

    sections: list[tuple[str, str]] = []
    last_end, current_heading = 0, ""
    for match in HEADING.finditer(body):
        segment = body[last_end:match.start()].strip()
        if segment:
            sections.append((current_heading, segment))
        current_heading = match.group(2).strip()
        last_end = match.end()
    tail = body[last_end:].strip()
    if tail:
        sections.append((current_heading, tail))
    if not sections and body.strip():
        sections = [("", body.strip())]

    chunks: list[Chunk] = []
    ordinal = 0
    for heading, segment in sections:
        segment = WIKILINK.sub(r"\1", segment)
        segment = MD_LINK.sub(r"\1", segment)
        segment = re.sub(r"\s+", " ", segment).strip()
        if not segment:
            continue
        if len(segment) <= max_chars:
            chunks.append(Chunk(path, heading, ordinal, segment))
            ordinal += 1
            continue
        sentences = re.split(r"(?<=[.!?])\s+", segment)
        buffer = ""
        for sentence in sentences:
            if len(buffer) + len(sentence) + 1 > max_chars and buffer:
                chunks.append(Chunk(path, heading, ordinal, buffer.strip()))
                ordinal += 1
                buffer = sentence
            else:
                buffer = f"{buffer} {sentence}".strip()
        if buffer.strip():
            chunks.append(Chunk(path, heading, ordinal, buffer.strip()))
            ordinal += 1
    return chunks


def file_hash(path: Path) -> str:
    digest = hashlib.blake2b(digest_size=16)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def needs_reindex(db: sqlite3.Connection, rel: str, path: Path) -> bool:
    row = db.execute("SELECT mtime, hash FROM docs WHERE path = ?", (rel,)).fetchone()
    if row is None:
        return True
    if abs(row["mtime"] - path.stat().st_mtime) < 0.001:
        return False
    return row["hash"] != file_hash(path)


def index_file(db: sqlite3.Connection, root: Path, path: Path, layer: str,
               embedder: Embedder | None, has_vec: bool) -> int:
    rel = str(path.relative_to(root))
    text = path.read_text(encoding="utf-8", errors="replace")
    body, fm = strip_frontmatter(text)

    tags = sorted(set(TAG.findall(body)) | {
        t.strip() for t in str(fm.get("tags", "")).split(",") if t.strip()
    })
    links = sorted(set(WIKILINK.findall(text)))
    title = fm.get("title") or (HEADING.search(body).group(2) if HEADING.search(body) else path.stem)

    old = db.execute("SELECT id FROM chunks WHERE path = ?", (rel,)).fetchall()
    if old and has_vec:
        db.executemany("DELETE FROM chunks_vec WHERE chunk_id = ?", [(r["id"],) for r in old])
    db.execute("DELETE FROM chunks WHERE path = ?", (rel,))

    db.execute(
        "INSERT OR REPLACE INTO docs(path, layer, title, tags, links, mtime, hash, indexed) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (rel, layer, title, ",".join(tags), ",".join(links),
         path.stat().st_mtime, file_hash(path), time.time()),
    )

    chunks = chunk_document(rel, text)
    if not chunks:
        return 0

    ids: list[int] = []
    for chunk in chunks:
        cursor = db.execute(
            "INSERT INTO chunks(path, heading, ordinal, text) VALUES (?, ?, ?, ?)",
            (chunk.doc_path, chunk.heading, chunk.ordinal, chunk.text),
        )
        ids.append(cursor.lastrowid)

    if has_vec and embedder and embedder.available:
        vectors = embedder.encode([f"{c.heading}\n{c.text}".strip() for c in chunks])
        if vectors is not None:
            normalized = l2_normalize(vectors)
            db.executemany(
                "INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?, ?)",
                [(cid, vec.tobytes()) for cid, vec in zip(ids, normalized)],
            )
    return len(chunks)


def prune_missing(db: sqlite3.Connection, roots: dict[str, Path], has_vec: bool) -> int:
    removed = 0
    for row in db.execute("SELECT path, layer FROM docs").fetchall():
        root = roots.get(row["layer"])
        if root and (root / row["path"]).is_file():
            continue
        if has_vec:
            stale = db.execute("SELECT id FROM chunks WHERE path = ?", (row["path"],)).fetchall()
            db.executemany("DELETE FROM chunks_vec WHERE chunk_id = ?", [(r["id"],) for r in stale])
        db.execute("DELETE FROM chunks WHERE path = ?", (row["path"],))
        db.execute("DELETE FROM docs WHERE path = ?", (row["path"],))
        removed += 1
    return removed


def fts_query(raw: str) -> str:
    """FTS5 MATCH syntax is unforgiving; a user query is not a query language.

    Strip the operators, OR the terms, prefix-match the last one so partial words still hit.
    """
    terms = [t for t in FTS_SPECIAL.sub(" ", raw).split() if len(t) > 1]
    if not terms:
        return ""
    quoted = [f'"{t}"' for t in terms[:-1]]
    quoted.append(f'"{terms[-1]}"*')
    return " OR ".join(quoted)


def search_bm25(db: sqlite3.Connection, query: str, limit: int) -> list[tuple[int, float]]:
    match = fts_query(query)
    if not match:
        return []
    try:
        rows = db.execute(
            "SELECT rowid, bm25(chunks_fts) AS score FROM chunks_fts "
            "WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?",
            (match, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [(row["rowid"], row["score"]) for row in rows]


def search_vec(db: sqlite3.Connection, query: str, embedder: Embedder, limit: int) -> list[tuple[int, float]]:
    vectors = embedder.encode([query])
    if vectors is None:
        return []
    query_vec = l2_normalize(vectors)[0]
    try:
        rows = db.execute(
            "SELECT chunk_id, distance FROM chunks_vec "
            "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (query_vec.tobytes(), limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    # Drop near-orthogonal neighbours: KNN always returns k rows, but a row past the ceiling is
    # noise, and letting it into RRF is how the arm invents matches for unrelated queries.
    return [(row["chunk_id"], row["distance"]) for row in rows if row["distance"] < VEC_MAX_DISTANCE]


def rrf(bm25: list[tuple[int, float]], vec: list[tuple[int, float]], k: int = RRF_K):
    """Reciprocal Rank Fusion: score = Σ 1/(k + rank).

    Rank-based, so the two arms need no score calibration — which is precisely what lets the vector
    arm be optional (ADR-0007).
    """
    scores: dict[int, float] = {}
    ranks: dict[int, dict[str, int]] = {}
    for arm, results in (("bm25", bm25), ("vec", vec)):
        for rank, (chunk_id, _) in enumerate(results, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            ranks.setdefault(chunk_id, {})[arm] = rank
    return scores, ranks


def search(db: sqlite3.Connection, query: str, limit: int = 5, has_vec: bool = False,
           embedder: Embedder | None = None, layer: str | None = None) -> list[Hit]:
    pool = max(limit * 6, 30)
    bm25 = search_bm25(db, query, pool)
    vec = search_vec(db, query, embedder, pool) if (has_vec and embedder and embedder.available) else []

    if not bm25 and not vec:
        return []

    scores, ranks = rrf(bm25, vec)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

    hits: list[Hit] = []
    for chunk_id, score in ordered:
        row = db.execute(
            "SELECT c.path, c.heading, c.text, d.layer, d.title "
            "FROM chunks c JOIN docs d ON d.path = c.path WHERE c.id = ?",
            (chunk_id,),
        ).fetchone()
        if row is None:
            continue
        if layer and row["layer"] != layer:
            continue
        hits.append(Hit(
            path=row["path"],
            heading=row["heading"] or row["title"] or "",
            snippet=row["text"][:400],
            score=score,
            bm25_rank=ranks[chunk_id].get("bm25"),
            vec_rank=ranks[chunk_id].get("vec"),
        ))
        if len(hits) >= limit:
            break
    return hits


def stats(db: sqlite3.Connection, has_vec: bool) -> dict:
    docs = db.execute("SELECT COUNT(*) AS n FROM docs").fetchone()["n"]
    chunks = db.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]
    by_layer = {
        row["layer"]: row["n"]
        for row in db.execute("SELECT layer, COUNT(*) AS n FROM docs GROUP BY layer").fetchall()
    }
    vectors = 0
    if has_vec:
        try:
            vectors = db.execute("SELECT COUNT(*) AS n FROM chunks_vec").fetchone()["n"]
        except sqlite3.OperationalError:
            vectors = 0
    return {"docs": docs, "chunks": chunks, "vectors": vectors, "by_layer": by_layer,
            "vector_arm": has_vec}
