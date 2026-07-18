#!/usr/bin/env python3
"""Test suite for the agentic OS. Real behaviour, no mocks.

Hooks are driven with the payload shapes Claude Code actually sends and asserted on the protocol
they actually answer with. The commit gate runs against a real git repository built in a temp dir.
Retrieval runs against a real vault with real files.

The one substitution: model2vec's model cannot be fetched in every environment, so the vector arm
is exercised with feature-hashed embeddings — real float32 vectors of the right dimension through
the identical SQL. What that proves is the schema, the KNN query and the fusion; model2vec swaps in
better vectors, not different plumbing (ADR-0007).

Usage:
    python3 tests/run_tests.py
    python3 tests/run_tests.py -v
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATES = ROOT / "plugins" / "governance-gates" / "hooks" / "scripts"
CORE = ROOT / "plugins" / "core-orchestration" / "scripts"
MEMORY = ROOT / "plugins" / "memory-obsidian" / "scripts"
SELF = ROOT / "plugins" / "self-evolution" / "scripts"

VERBOSE = "-v" in sys.argv
PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        if VERBOSE:
            print(f"  ok   {name}")
    else:
        FAILED.append((name, detail))
        print(f"  FAIL {name}" + (f"\n         {detail}" if detail else ""))


def run_hook(script: str, payload: dict, env: dict | None = None) -> tuple[int, str, str]:
    environment = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(GATES.parents[1]), **(env or {})}
    result = subprocess.run(
        [sys.executable, str(GATES / script)],
        input=json.dumps(payload), capture_output=True, text=True, env=environment, timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


GUARDRAILS = ROOT / "plugins" / "core-guardrails" / "hooks" / "scripts"


def run_guardrail(relpath: str, payload: dict, env: dict | None = None) -> tuple[int, str, str]:
    """core-guardrails hooks import a sibling `lib` package, so they run with the scripts dir
    on PYTHONPATH rather than from the governance-gates root."""
    environment = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(GUARDRAILS.parents[1]),
        "PYTHONPATH": str(GUARDRAILS),
        **(env or {}),
    }
    result = subprocess.run(
        [sys.executable, str(GUARDRAILS / relpath)],
        input=json.dumps(payload), capture_output=True, text=True, env=environment, timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def decision(stdout: str) -> str | None:
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    if "hookSpecificOutput" in data:
        return data["hookSpecificOutput"].get("permissionDecision")
    return data.get("decision")


# ── secret guard ─────────────────────────────────────────────────────────────────────────────

def test_secret_guard() -> None:
    """Content layer only — ADR-0022 moved the path and bash layers to
    core-guardrails/PreToolUse/20_security_gate.py, which owns them for the whole OS.
    The cases below assert that this gate no longer duplicates them: a secret *path* must
    now pass through here untouched, because denying it twice is the bug ADR-0022 fixes."""
    print("\nsecret_guard")
    cases = [
        ("passes .env read to the runtime gate",
         {"tool_name": "Read", "tool_input": {"file_path": "/p/.env"}}, None),
        ("passes ssh key to the runtime gate",
         {"tool_name": "Read", "tool_input": {"file_path": "/home/u/.ssh/id_rsa"}}, None),
        ("allows source file", {"tool_name": "Read", "tool_input": {"file_path": "/p/main.py"}}, None),
        ("denies anthropic key in content",
         {"tool_name": "Write", "tool_input": {"file_path": "/p/c.py",
          "content": 'K="sk-ant-api03-' + "A" * 40 + '"'}}, "deny"),
        ("denies github token in content",
         {"tool_name": "Write", "tool_input": {"file_path": "/p/c.py", "content": 'T="ghp_' + "b" * 40 + '"'}}, "deny"),
        ("denies aws key id in content",
         {"tool_name": "Write", "tool_input": {"file_path": "/p/c.py", "content": "id = AKIAIOSFODNN7EXAMPLE"}}, "deny"),
        ("denies private key block",
         {"tool_name": "Write", "tool_input": {"file_path": "/p/k.txt",
          "content": "-----BEGIN RSA PRIVATE KEY-----\nMIIE"}}, "deny"),
        ("allows ordinary code",
         {"tool_name": "Write", "tool_input": {"file_path": "/p/m.py", "content": "def add(a, b):\n    return a + b"}}, None),
        ("allows env var reference",
         {"tool_name": "Write", "tool_input": {"file_path": "/p/m.py",
          "content": 'key = os.environ["ANTHROPIC_API_KEY"]'}}, None),
        ("passes cat .env to the runtime gate",
         {"tool_name": "Bash", "tool_input": {"command": "cat /p/.env"}}, None),
        ("denies a live key echoed into a file",
         {"tool_name": "Bash", "tool_input": {"command": 'echo "ghp_' + "c" * 40 + '" > /p/t'}}, "deny"),
        ("allows ordinary bash", {"tool_name": "Bash", "tool_input": {"command": "ls -la && git status"}}, None),
        ("allows grep in source", {"tool_name": "Bash", "tool_input": {"command": "grep -r TODO src/"}}, None),
    ]
    for name, payload, expected in cases:
        rc, out, _ = run_hook("secret_guard.py", payload)
        got = decision(out)
        check(f"secret_guard: {name}", rc == 0 and got == expected,
              f"exit={rc} decision={got} want={expected}")

    rc, out, _ = run_hook("secret_guard.py", {"garbage": True})
    check("secret_guard: malformed payload does not block", rc == 0 and decision(out) is None,
          f"exit={rc}")

    rc, out, _ = run_hook("secret_guard.py", {
        "tool_name": "Write",
        "tool_input": {"file_path": "/p/c.py", "content": 'T="ghp_' + "d" * 40 + '"'},
    })
    reason = json.loads(out)["hookSpecificOutput"].get("permissionDecisionReason", "")
    check("secret_guard: deny carries an actionable reason", len(reason) > 40 and "secret-guard" in reason)


# ── security gate (the runtime owner of paths and bash, ADR-0022) ─────────────────────────────

def test_security_gate() -> None:
    """ADR-0022 moved secret paths and dangerous bash out of secret_guard and into this gate.
    These cases are the coverage that moved with them — without them the deconfliction would
    have silently deleted the only tests for secret-path denial."""
    print("\nsecurity_gate")
    cases = [
        ("denies .env read", {"tool_name": "Read", "tool_input": {"file_path": "/p/.env"}}, "deny"),
        ("denies ssh key", {"tool_name": "Read", "tool_input": {"file_path": "/home/u/.ssh/id_rsa"}}, "deny"),
        ("denies aws credentials",
         {"tool_name": "Read", "tool_input": {"file_path": "/home/u/.aws/credentials"}}, "deny"),
        ("allows source file", {"tool_name": "Read", "tool_input": {"file_path": "/p/main.py"}}, None),
        ("denies cat .env", {"tool_name": "Bash", "tool_input": {"command": "cat /p/.env"}}, "deny"),
        ("allows ordinary bash",
         {"tool_name": "Bash", "tool_input": {"command": "ls -la && git status"}}, None),
    ]
    for name, payload, expected in cases:
        rc, out, err = run_guardrail("PreToolUse/20_security_gate.py", payload)
        got = decision(out)
        check(f"security_gate: {name}", rc == 0 and got == expected,
              f"exit={rc} decision={got} want={expected} stderr={err[:200]}")

    # Fails closed: a gate that crashes open is worse than no gate.
    rc, out, _ = run_guardrail("PreToolUse/20_security_gate.py", {"garbage": True})
    check("security_gate: malformed payload does not crash open",
          rc == 0 and decision(out) in (None, "deny"), f"exit={rc} decision={decision(out)}")


# ── commit + ADR gate, against a real repo ───────────────────────────────────────────────────

def git(*args: str, cwd: Path) -> str:
    return subprocess.run(("git", *args), cwd=cwd, capture_output=True, text=True).stdout.strip()


def build_repo(tmp: Path) -> Path:
    """A real marketplace repo with real git history — the gate parses porcelain and diffs, so a
    fake would prove nothing."""
    repo = tmp / "market"
    (repo / ".claude-plugin").mkdir(parents=True)
    (repo / "plugins" / "demo" / ".claude-plugin").mkdir(parents=True)
    (repo / "plugins" / "demo" / "skills" / "thing").mkdir(parents=True)
    (repo / "adr").mkdir()

    (repo / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
        "name": "test-market",
        "plugins": [{"name": "demo", "source": "./plugins/demo"}],
    }, indent=2))
    (repo / "plugins" / "demo" / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": "demo", "version": "1.0.0", "description": "test fixture",
    }, indent=2))
    (repo / "plugins" / "demo" / "skills" / "thing" / "SKILL.md").write_text(
        "---\nname: thing\ndescription: A fixture skill with a description long enough to clear the "
        "validator's minimum length check for trigger surfaces.\nmetadata:\n  version: 1.0.0\n---\n\n# Thing\n\nBody.\n"
    )
    (repo / "plugins" / "demo" / "skills" / "thing" / "skill.json").write_text(json.dumps({
        "name": "thing", "version": "1.0.0", "description": "fixture", "stability": "stable",
    }, indent=2))

    git("init", "-q", cwd=repo)
    git("config", "user.email", "test@example.com", cwd=repo)
    git("config", "user.name", "Test", cwd=repo)
    git("config", "commit.gpgsign", "false", cwd=repo)
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "chore: initial fixture", cwd=repo)
    return repo


def test_commit_gate(tmp: Path) -> None:
    print("\ncommit_adr_gate")
    repo = build_repo(tmp)
    env = {"CLAUDE_PLUGIN_DATA": str(tmp / "data")}

    rc, out, _ = run_hook("commit_adr_gate.py", {"session_id": "s1", "cwd": str(repo)}, env)
    check("commit_gate: clean tree passes", rc == 0 and decision(out) is None, f"exit={rc} out={out[:80]}")

    skill = repo / "plugins" / "demo" / "skills" / "thing" / "SKILL.md"
    skill.write_text(skill.read_text().replace("Body.", "Body, edited."))
    rc, out, _ = run_hook("commit_adr_gate.py", {"session_id": "s1", "cwd": str(repo)}, env)
    check("commit_gate: dirty core logic blocks", rc == 0 and decision(out) == "block", f"exit={rc}")

    reason = json.loads(out).get("reason", "")
    check("commit_gate: block names the component", "skill/thing" in reason, reason[:120])
    check("commit_gate: block gives the git commands", "git add" in reason and "git commit" in reason)

    rc, out, _ = run_hook("commit_adr_gate.py",
                          {"session_id": "s1", "cwd": str(repo), "stop_hook_active": True}, env)
    check("commit_gate: stop_hook_active prevents a loop", rc == 0 and decision(out) is None, f"exit={rc}")

    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "docs(skill/thing): clarify body", cwd=repo)
    rc, out, _ = run_hook("commit_adr_gate.py", {"session_id": "s1", "cwd": str(repo)}, env)
    check("commit_gate: committed tree passes", rc == 0 and decision(out) is None, f"exit={rc}")

    readme = repo / "README.md"
    readme.write_text("# Not core logic\n")
    rc, out, _ = run_hook("commit_adr_gate.py", {"session_id": "s1", "cwd": str(repo)}, env)
    check("commit_gate: non-core files are not gated", rc == 0 and decision(out) is None, f"exit={rc}")
    readme.unlink()

    # A contract change with no ADR must demand one.
    skill.write_text(skill.read_text().replace(
        "metadata:", "allowed-tools: Bash\nmetadata:"))
    rc, out, _ = run_hook("commit_adr_gate.py", {"session_id": "s1", "cwd": str(repo)}, env)
    reason = json.loads(out).get("reason", "") if decision(out) == "block" else ""
    check("commit_gate: contract change demands an ADR",
          "decision record" in reason.lower(), reason[:120])
    git("checkout", "--", ".", cwd=repo)

    rc, out, _ = run_hook("commit_adr_gate.py", {"session_id": "s1", "cwd": str(tmp)}, env)
    check("commit_gate: outside a marketplace is a no-op", rc == 0 and decision(out) is None, f"exit={rc}")


def test_trackers(tmp: Path) -> None:
    print("\ncore_change_tracker + audit_logger")
    repo = build_repo(tmp / "t2") if (tmp / "t2").mkdir(exist_ok=True) or True else None
    data = tmp / "data2"
    env = {"CLAUDE_PLUGIN_DATA": str(data)}
    skill = repo / "plugins" / "demo" / "skills" / "thing" / "SKILL.md"

    rc, _, _ = run_hook("core_change_tracker.py", {
        "session_id": "sess-abc", "cwd": str(repo), "tool_name": "Edit",
        "tool_input": {"file_path": str(skill)},
    }, env)
    ledger = data / "sessions" / "sess-abc.json"
    check("tracker: records the touched component", rc == 0 and ledger.is_file(), f"exit={rc}")
    if ledger.is_file():
        state = json.loads(ledger.read_text())
        check("tracker: component id is correct", "skill/thing" in state.get("components", {}),
              str(list(state.get("components", {}))))

    rc, _, _ = run_hook("audit_logger.py", {
        "session_id": "sess-abc", "cwd": str(repo), "tool_name": "Bash",
        "tool_input": {"command": "git status --porcelain"},
        "tool_response": {"stdout": "", "is_error": False},
    }, env)
    trails = list((data / "audit").glob("*.jsonl")) if (data / "audit").is_dir() else []
    check("audit: writes a trail line", rc == 0 and bool(trails), f"exit={rc}")
    if trails:
        record = json.loads(trails[0].read_text().splitlines()[0])
        check("audit: records the tool", record.get("tool") == "Bash", str(record))
        check("audit: records a summary, not the payload",
              record.get("summary") == "git status --porcelain" and "stdout" not in record)

    rc, _, _ = run_hook("audit_logger.py", {
        "session_id": "s", "cwd": str(repo), "tool_name": "Write",
        "tool_input": {"file_path": "/p/x.py", "content": "sk-ant-api03-" + "Z" * 40},
        "tool_response": {"is_error": False},
    }, env)
    body = "\n".join(t.read_text() for t in (data / "audit").glob("*.jsonl"))
    check("audit: never records file content", "sk-ant-api03" not in body)


def test_manifest_validator(tmp: Path) -> None:
    print("\nmanifest_validator")
    repo = build_repo(tmp / "t3") if (tmp / "t3").mkdir(exist_ok=True) or True else None
    shutil.copytree(CORE, repo / "plugins" / "core-orchestration" / "scripts")
    env = {"CLAUDE_PLUGIN_DATA": str(tmp / "data3")}

    skill_json = repo / "plugins" / "demo" / "skills" / "thing" / "skill.json"
    rc, out, _ = run_hook("manifest_validator.py", {
        "cwd": str(repo), "tool_name": "Edit", "tool_input": {"file_path": str(skill_json)},
    }, env)
    check("validator: valid manifest passes", rc == 0, f"exit={rc}")

    skill_json.write_text(json.dumps({"name": "thing", "version": "9.9.9", "stability": "stable"}))
    rc, out, err = run_hook("manifest_validator.py", {
        "cwd": str(repo), "tool_name": "Edit", "tool_input": {"file_path": str(skill_json)},
    }, env)
    check("validator: version drift blocks with exit 2", rc == 2, f"exit={rc}")
    check("validator: block explains the drift", "drift" in err.lower(), err[:120])

    rc, _, _ = run_hook("manifest_validator.py", {
        "cwd": str(repo), "tool_name": "Edit", "tool_input": {"file_path": str(repo / "README.md")},
    }, env)
    check("validator: ignores non-core files", rc == 0, f"exit={rc}")


# ── retrieval ────────────────────────────────────────────────────────────────────────────────

class HashEmbedder:
    """Feature hashing into 256 dims, L2-normalised — the hashing trick. Real vectors through the
    real SQL; model2vec substitutes better ones, not a different code path."""
    available = True
    reason = ""

    def load(self) -> bool:
        return True

    def encode(self, texts, max_length=512):
        import numpy as np
        out = np.zeros((len(texts), 256), dtype=np.float32)
        for i, text in enumerate(texts):
            for token in text.lower().split():
                h = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=4).digest(), "little")
                out[i, h % 256] += 1.0 if h & 1 else -1.0
            norm = np.linalg.norm(out[i])
            if norm > 0:
                out[i] /= norm
        return out


def test_retrieval(tmp: Path) -> None:
    print("\nretrieval")
    sys.path.insert(0, str(MEMORY))
    from vaultdb import chunk_document, connect, index_file, init_schema, needs_reindex, rrf, search

    vault = tmp / "vault"
    (vault / "notes").mkdir(parents=True)
    (vault / "notes" / "router.md").write_text(
        "---\ntitle: Cascade Router\ntags: [architecture]\n---\n# Cascade Router\n"
        "Four-tier model selection cutting token cost by 94 percent.\n\n"
        "## Escalation\nTier 1 classifies. Tier 4 reasons. The 2-to-3 gate holds the savings.\n"
    )
    (vault / "notes" / "metrics.md").write_text(
        "---\ntitle: Metrics Platform\n---\n# Metrics Platform\n"
        "TimescaleDB hypertables with a 90-day compression policy.\n"
    )

    chunks = chunk_document("x.md", (vault / "notes" / "router.md").read_text())
    check("chunker: splits on headings", len(chunks) == 2, f"got {len(chunks)}")
    check("chunker: strips frontmatter", all("title:" not in c.text for c in chunks))
    check("chunker: keeps the heading", any(c.heading == "Escalation" for c in chunks),
          str([c.heading for c in chunks]))

    db, has_vec = connect(tmp / "index.db")
    init_schema(db, has_vec)
    embedder = HashEmbedder() if has_vec else None
    total = sum(index_file(db, vault, p, "L3-knowledge", embedder, has_vec)
                for p in sorted(vault.rglob("*.md")))
    db.commit()
    check("index: indexes every chunk", total == 3, f"got {total}")

    check("index: skips unchanged files",
          not needs_reindex(db, "notes/router.md", vault / "notes" / "router.md"))

    hits = search(db, "token cost tier", limit=3, has_vec=has_vec, embedder=embedder)
    check("search: finds by keyword", bool(hits) and "router" in hits[0].path, str([h.path for h in hits]))

    hits = search(db, "hypertable compression", limit=2, has_vec=has_vec, embedder=embedder)
    check("search: finds a single-note term", bool(hits) and "metrics" in hits[0].path,
          str([h.path for h in hits]))

    # "No match returns empty" is asserted on the BM25-only path: it is deterministic (no term
    # overlap → no FTS rows) and is the actual production mode wherever the embedding model is
    # absent. The vector arm's no-match behaviour is governed by the distance threshold, tested
    # in isolation below — the feature-hashing embedder used here is too crude to guarantee
    # orthogonality for arbitrary tokens (a token can hash-collide into a live bucket), which
    # would make a combined assertion flaky rather than meaningful.
    check("search: BM25-only empty on no match",
          search(db, "kubernetes helm istio", limit=3, has_vec=False, embedder=None) == [])

    bm25_only = search(db, "token cost", limit=2, has_vec=False, embedder=None)
    check("search: BM25-only path works without the vector arm", bool(bm25_only))

    scores, ranks = rrf([(1, 0.5), (2, 0.4)], [(2, 0.1), (3, 0.2)])
    expected = 1 / 61 + 1 / 62
    check("rrf: arithmetic is exact", abs(scores[2] - expected) < 1e-9, f"{scores[2]} vs {expected}")
    check("rrf: a hit in both arms outranks either", scores[2] > scores[1] and scores[2] > scores[3])
    check("rrf: tracks which arm contributed", ranks[2] == {"bm25": 2, "vec": 1}, str(ranks[2]))

    if has_vec:
        import numpy as np
        from vaultdb import EMBED_DIM, VEC_MAX_DISTANCE, search_vec

        count = db.execute("SELECT COUNT(*) FROM chunks_vec").fetchone()[0]
        check("sqlite-vec: vector per chunk", count == 3, f"got {count}")
        raw = db.execute(
            "SELECT chunk_id, distance FROM chunks_vec WHERE embedding MATCH ? AND k = 2 ORDER BY distance",
            (embedder.encode(["token cost"])[0].tobytes(),),
        ).fetchall()
        check("sqlite-vec: KNN returns k rows, distance-ordered",
              len(raw) == 2 and raw[0][1] <= raw[1][1], str(raw))
        hits = search(db, "token cost tier", limit=3, has_vec=True, embedder=embedder)
        check("sqlite-vec: vector arm contributes to fused results", any(h.vec_rank for h in hits))

        # Distance threshold, tested with controlled unit vectors so the result depends on the
        # geometry, not on hash-collision luck: one basis vector aligned with the query (distance
        # 0), one orthogonal (distance √2 ≈ 1.414). The threshold must keep the first and drop the
        # second — this is what lets a genuinely unrelated query return nothing (ADR-0007).
        probe = tmp / "probe.db"
        pdb, _ = connect(probe)
        init_schema(pdb, True)
        pdb.execute("INSERT INTO docs(path,layer,title,tags,links,mtime,hash,indexed) "
                    "VALUES ('a.md','L3','a','','',0,'x',0),('b.md','L3','b','','',0,'y',0)")
        pdb.execute("INSERT INTO chunks(id,path,heading,ordinal,text) "
                    "VALUES (1,'a.md','',0,'aligned'),(2,'b.md','',0,'orthogonal')")
        aligned = np.zeros(EMBED_DIM, np.float32); aligned[0] = 1.0
        orthogonal = np.zeros(EMBED_DIM, np.float32); orthogonal[1] = 1.0
        pdb.execute("INSERT INTO chunks_vec(chunk_id,embedding) VALUES (1,?),(2,?)",
                    (aligned.tobytes(), orthogonal.tobytes()))
        pdb.commit()

        class FixedEmbedder:
            available = True
            reason = ""
            def load(self): return True
            def encode(self, texts, max_length=512):
                v = np.zeros((1, EMBED_DIM), np.float32); v[0, 0] = 1.0
                return v

        kept = search_vec(pdb, "q", FixedEmbedder(), 2)
        kept_ids = [cid for cid, _ in kept]
        check("threshold: keeps the aligned vector", 1 in kept_ids, str(kept))
        check("threshold: drops the orthogonal vector (distance √2 > ceiling)",
              2 not in kept_ids, f"ceiling={VEC_MAX_DISTANCE} kept={kept}")
        pdb.close()
    else:
        print("  --   sqlite-vec not loadable; vector arm assertions skipped")
    db.close()


def test_doctor(tmp: Path) -> None:
    print("\ndoctor")
    result = subprocess.run([sys.executable, str(CORE / "doctor.py"), "--json"],
                            capture_output=True, text=True, cwd=ROOT)
    check("doctor: this marketplace is clean", result.returncode == 0,
          result.stdout[-400:] if result.stdout else result.stderr[-200:])
    if result.stdout:
        report = json.loads(result.stdout)
        check("doctor: checked a real number of components", report["checked"] >= 20,
              f"checked={report.get('checked')}")

    broken = tmp / "broken"
    shutil.copytree(build_repo(tmp / "t4").parent / "market", broken / "market")
    market = broken / "market"
    (market / "plugins" / "demo" / ".claude-plugin" / "skills").mkdir(parents=True)
    result = subprocess.run([sys.executable, str(CORE / "doctor.py"), "--root", str(market), "--json"],
                            capture_output=True, text=True)
    findings = json.loads(result.stdout)["errors"] if result.stdout else []
    check("doctor: catches components misfiled under .claude-plugin/",
          result.returncode == 1 and any("plugin root" in e["message"] for e in findings),
          str(findings)[:200])


def test_self_evolution(tmp: Path) -> None:
    if VERBOSE:
        print("\nself-evolution")

    # --- eval harness + regression detection, on a controlled mini eval-dir (no recursion into
    #     the real suite): a marker file toggles one eval, so we can force a regression on demand.
    market = tmp / "se-market"
    (market / ".claude-plugin").mkdir(parents=True)
    (market / ".claude-plugin" / "marketplace.json").write_text('{"name":"t","plugins":[]}')
    marker = market / "MARKER"
    marker.write_text("present")

    proot = tmp / "se-plugin"
    (proot / "evals").mkdir(parents=True)
    (proot / "evals" / "always-pass.json").write_text(json.dumps({
        "id": "always-pass", "capability": "control", "kind": "invariant",
        "description": "always passes",
        "verifier": {"type": "exit_zero", "command": ["python3", "-c", "raise SystemExit(0)"]},
        "weight": 1.0,
    }))
    (proot / "evals" / "toggle.json").write_text(json.dumps({
        "id": "toggle", "capability": "control", "kind": "invariant",
        "description": "passes iff the marker exists",
        "verifier": {"type": "exit_zero", "command": [
            "python3", "-c",
            "import os,sys; sys.exit(0 if os.path.exists(os.path.join('${REPO_ROOT}','MARKER')) else 1)"]},
        "weight": 1.0,
    }))

    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(proot), "CLAUDE_PLUGIN_DATA": str(tmp / "se-data")}

    def evalctl(*args: str) -> tuple[int, dict]:
        result = subprocess.run(
            [sys.executable, str(SELF / "evalctl.py"), "--root", str(market), *args],
            capture_output=True, text=True, env=env, timeout=60)
        payload = {}
        if "--json" in args and result.stdout.strip():
            payload = json.loads(result.stdout)
        return result.returncode, payload

    # green state: both pass, aggregate 1.0
    code, card = evalctl("--json", "--no-ledger")
    check("evalctl: runs the suite and scores", card.get("aggregate") == 1.0, str(card.get("aggregate")))
    check("evalctl: green suite exits 0", code == 0, f"exit {code}")

    # snapshot the green state as baseline
    subprocess.run([sys.executable, str(SELF / "evalctl.py"), "--root", str(market), "--set-baseline"],
                   capture_output=True, text=True, env=env, timeout=30)
    check("evalctl: baseline is written", (proot / "evals" / "baseline.json").is_file())

    # break the toggle eval → regression must be caught, exit 1
    marker.unlink()
    code, card = evalctl("--json", "--no-ledger")
    regs = {r["id"] for r in card.get("regressions", [])}
    check("evalctl: detects a regression against baseline", "toggle" in regs, str(card.get("regressions")))
    check("evalctl: regression exits non-zero (revert signal)", code == 1, f"exit {code}")
    check("evalctl: unaffected eval stays green",
          any(r["id"] == "always-pass" and r["pass"] for r in card.get("results", [])))

    # --- experience miner: a planted workflow must surface
    audit = tmp / "se-audit"
    audit.mkdir()
    lines = []
    ts = 0
    for s in range(4):
        for tool in ("Edit", "Bash", "Edit"):
            ts += 1
            lines.append(json.dumps({"ts": f"2026-07-16T10:00:{ts:02d}", "session": f"s{s}",
                                     "tool": tool, "ok": True, "components": ["skill/x"]}))
    (audit / "trail.jsonl").write_text("\n".join(lines) + "\n")
    result = subprocess.run([sys.executable, str(SELF / "mine.py"), "--audit-dir", str(audit),
                             "--json", "--min-support", "3", "--root", str(ROOT)],
                            capture_output=True, text=True, timeout=30)
    mined = json.loads(result.stdout)
    workflows = mined["signals"]["workflows"]
    check("mine: reconstructs sessions from the trail", mined["meta"]["sessions_analysed"] == 4)
    check("mine: surfaces the planted workflow",
          any(w["pattern"] == ["Edit", "Bash", "Edit"] and w["sessions"] == 4 for w in workflows),
          str(workflows))

    # empty trail → no crash, no signals
    empty = tmp / "se-empty"
    empty.mkdir()
    result = subprocess.run([sys.executable, str(SELF / "mine.py"), "--audit-dir", str(empty),
                             "--json", "--root", str(ROOT)], capture_output=True, text=True, timeout=30)
    empty_mined = json.loads(result.stdout)
    check("mine: empty trail yields no signals",
          empty_mined["meta"]["sessions_analysed"] == 0 and not empty_mined["signals"]["workflows"])

    # --- proposal engine: a regression must rank above a workflow
    sig_file = tmp / "sig.json"
    sig_file.write_text(json.dumps({"meta": {"sessions_analysed": 4}, "signals": {
        "workflows": [{"type": "workflow", "pattern": ["Edit", "Bash"], "sessions": 4,
                       "occurrences": 4, "support": 1.0, "suggests": "x"}],
        "failures": [], "co_edits": [], "churn": []}}))
    score_file = tmp / "score.json"
    score_file.write_text(json.dumps({"aggregate": 0.9, "regressions": [{"id": "toggle", "was": 1.0, "now": 0.5}],
                                      "results": [{"id": "toggle", "capability": "control", "pass": False,
                                                   "score": 0.5, "detail": "x"}]}))
    result = subprocess.run([sys.executable, str(SELF / "propose.py"), "--signals", str(sig_file),
                             "--scorecard", str(score_file), "--json", "--root", str(ROOT)],
                            capture_output=True, text=True, timeout=30)
    proposals = json.loads(result.stdout)["proposals"]
    check("propose: produces proposals from signals and regressions", len(proposals) == 2, str(len(proposals)))
    check("propose: ranks the regression first",
          proposals and proposals[0]["kind"] == "fix" and "toggle" in proposals[0]["id"],
          proposals[0]["id"] if proposals else "none")
    check("propose: every proposal requires an ADR",
          all(p["requires_adr"] for p in proposals))


def test_long_horizon(tmp: Path) -> None:
    if VERBOSE:
        print("\nlong-horizon")
    LH = ROOT / "plugins" / "long-horizon" / "scripts"

    # --- mission lifecycle as a black box against a temp dir
    mdir = tmp / "lh-missions"

    def mission(*args: str):
        return subprocess.run([sys.executable, str(LH / "mission.py"), "--dir", str(mdir), *args],
                              capture_output=True, text=True, timeout=30)

    created = mission("new", "Test goal", "--objective", "Both steps hold.", "--steps", "one;two",
                      "--priority", "high")
    check("mission: creates with steps and id", created.returncode == 0 and "m-0001" in created.stdout)
    check("mission: refuses completion with open steps", mission("complete", "m-0001").returncode == 1)
    advanced = mission("step-done", "m-0001", "1", "--note", "evidence")
    check("mission: advances a step with a note", advanced.returncode == 0 and "evidence" in advanced.stdout)
    blocked = mission("block", "m-0001", "--on", "an upstream key")
    check("mission: blocks with a required reason", blocked.returncode == 0)
    brief = mission("brief")
    check("mission: brief surfaces the blocker", "BLOCKED" in brief.stdout and "upstream key" in brief.stdout)
    check("mission: resumes from blocked", mission("resume", "m-0001").returncode == 0)
    mission("step-done", "m-0001", "2")
    check("mission: completes when all steps done", mission("complete", "m-0001").returncode == 0)
    check("mission: brief silent with nothing in flight", mission("brief").stdout.strip() == "")
    check("mission: ids never reused", "m-0002" in mission("new", "Second").stdout)

    # --- multi-plugin eval discovery: two plugins, each shipping an eval; per-spec root resolution
    market = tmp / "lh-market"
    for plugin, eval_id in (("alpha", "alpha-check"), ("beta", "beta-check")):
        base = market / "plugins" / plugin
        (base / ".claude-plugin").mkdir(parents=True)
        (base / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": plugin, "version": "1.0.0", "description": "x"}))
        (base / "evals" / "verifiers").mkdir(parents=True)
        (base / "evals" / "verifiers" / "ok.py").write_text(
            "import json, sys\n"
            f"print(json.dumps({{'pass': True, 'score': 1.0, 'detail': '{plugin} verifier ran'}}))\n")
        (base / "evals" / f"{eval_id}.json").write_text(json.dumps({
            "id": eval_id, "capability": plugin, "kind": "script", "description": "x",
            "verifier": {"type": "script",
                         "script": "${CLAUDE_PLUGIN_ROOT}/evals/verifiers/ok.py"}}))
    (market / ".claude-plugin").mkdir()
    (market / ".claude-plugin" / "marketplace.json").write_text('{"name":"t","plugins":[]}')

    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(market / "plugins" / "alpha"),
           "CLAUDE_PLUGIN_DATA": str(tmp / "lh-data")}
    result = subprocess.run([sys.executable, str(SELF / "evalctl.py"), "--root", str(market),
                             "--json", "--no-ledger"], capture_output=True, text=True, env=env, timeout=60)
    card = json.loads(result.stdout)
    ids = {r["id"] for r in card["results"]}
    check("evalctl: discovers evals across plugins", ids == {"alpha-check", "beta-check"}, str(ids))
    check("evalctl: resolves plugin root per spec",
          all(r["pass"] for r in card["results"]),
          str([(r["id"], r["detail"]) for r in card["results"] if not r["pass"]]))

    # duplicate eval ids across plugins must be rejected
    dupe = market / "plugins" / "beta" / "evals" / "dupe.json"
    dupe.write_text(json.dumps({"id": "alpha-check", "capability": "beta", "kind": "script",
                                "description": "x",
                                "verifier": {"type": "script",
                                             "script": "${CLAUDE_PLUGIN_ROOT}/evals/verifiers/ok.py"}}))
    clash = subprocess.run([sys.executable, str(SELF / "evalctl.py"), "--root", str(market),
                            "--json", "--no-ledger"], capture_output=True, text=True, env=env, timeout=60)
    check("evalctl: rejects duplicate eval ids across plugins",
          clash.returncode == 2 and "duplicate" in clash.stderr)
    dupe.unlink()

    # --- frontier ranking on controlled inputs
    model = tmp / "lh-model.json"
    model.write_text(json.dumps({
        "source": "fixture", "regressions": [],
        "measured": [{"capability": "weakcap", "score": 0.4, "trend": "down", "evals": ["a", "b"],
                      "weak": True, "thin_evidence": False}],
        "coverage": [{"plugin": "gapped", "version": "1.0.0", "components": 3, "evaluated": False}],
        "usage": []}))
    fdir = tmp / "lh-frontier-missions"
    subprocess.run([sys.executable, str(LH / "mission.py"), "--dir", str(fdir), "new", "Stalled",
                    "--steps", "x"], capture_output=True, text=True, timeout=20)
    subprocess.run([sys.executable, str(LH / "mission.py"), "--dir", str(fdir), "block", "m-0001",
                    "--on", "capability missing"], capture_output=True, text=True, timeout=20)
    result = subprocess.run([sys.executable, str(LH / "frontier.py"), "--model", str(model),
                             "--missions-dir", str(fdir), "--no-mine", "--json", "--root", str(ROOT)],
                            capture_output=True, text=True, timeout=30)
    agenda = json.loads(result.stdout)["items"]
    kinds = [item["kind"] for item in agenda]
    check("frontier: fuses all three evidence streams",
          {"weakness", "blocked-intent", "coverage-gap"} <= set(kinds), str(kinds))
    check("frontier: weakness ranks first", kinds and kinds[0] == "weakness", str(kinds))
    check("frontier: every item carries evidence", all(item.get("evidence") for item in agenda))


def test_autonomic_loop(tmp: Path) -> None:
    if VERBOSE:
        print("\nautonomic-loop")
    HOOKS = ROOT / "plugins" / "autonomic-loop" / "hooks" / "scripts"

    # temp market with a copied eval harness and a toggleable mini suite — no recursion into
    # the real suite, and a regression can be forced by deleting the marker file
    market = tmp / "au-market"
    (market / ".claude-plugin").mkdir(parents=True)
    (market / ".claude-plugin" / "marketplace.json").write_text('{"name":"t","plugins":[]}')
    se = market / "plugins" / "self-evolution"
    (se / ".claude-plugin").mkdir(parents=True)
    (se / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "self-evolution", "version": "1.1.0", "description": "x"}))
    (se / "scripts").mkdir()
    shutil.copy2(SELF / "evalctl.py", se / "scripts" / "evalctl.py")
    (se / "evals").mkdir()
    (se / "evals" / "always-pass.json").write_text(json.dumps({
        "id": "always-pass", "capability": "control", "kind": "invariant", "description": "x",
        "verifier": {"type": "exit_zero", "command": ["python3", "-c", "raise SystemExit(0)"]}}))
    (se / "evals" / "toggle.json").write_text(json.dumps({
        "id": "toggle", "capability": "control", "kind": "invariant", "description": "x",
        "verifier": {"type": "exit_zero", "command": [
            "python3", "-c",
            "import os,sys; sys.exit(0 if os.path.exists(os.path.join('${REPO_ROOT}','MARKER')) else 1)"]}}))
    (se / "evals" / "baseline.json").write_text(json.dumps({
        "ts": "t", "sha": "t", "aggregate": 1.0,
        "scores": {"always-pass": 1.0, "toggle": 1.0}, "by_capability": {"control": 1.0}}))
    (market / "MARKER").write_text("present")
    data = tmp / "au-data"

    def hook(script: str, payload: dict, extra: dict | None = None) -> tuple[int, str]:
        env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT / "plugins" / "autonomic-loop"),
               "CLAUDE_PLUGIN_DATA": str(data), **(extra or {})}
        env.pop("AGENTIC_OS_AUTONOMIC", None)
        if extra and "AGENTIC_OS_AUTONOMIC" in extra:
            env["AGENTIC_OS_AUTONOMIC"] = extra["AGENTIC_OS_AUTONOMIC"]
        result = subprocess.run([sys.executable, str(HOOKS / script)], input=json.dumps(payload),
                                capture_output=True, text=True, env=env, timeout=90)
        return result.returncode, result.stdout.strip()

    core_edit = {"session_id": "a1", "cwd": str(market),
                 "tool_input": {"file_path": str(se / "scripts" / "evalctl.py")}}
    hook("change_sentinel.py", core_edit)
    check("autonomic: sentinel marks a core edit", (data / "state" / "dirty-a1.json").is_file())
    hook("change_sentinel.py", {"session_id": "a2", "cwd": str(market),
                                "tool_input": {"file_path": str(market / "notes.md")}})
    check("autonomic: sentinel ignores a non-core edit",
          not (data / "state" / "dirty-a2.json").is_file())

    code, out = hook("verify_on_change.py", {"session_id": "none", "cwd": str(market)})
    check("autonomic: clean session stops silently", code == 0 and out == "")

    code, out = hook("verify_on_change.py", {"session_id": "a1", "cwd": str(market)})
    check("autonomic: green verify allows and clears the debt",
          code == 0 and out == "" and not (data / "state" / "dirty-a1.json").is_file())

    (market / "MARKER").unlink()
    hook("change_sentinel.py", {**core_edit, "session_id": "a3"})
    code, out = hook("verify_on_change.py", {"session_id": "a3", "cwd": str(market)})
    blocked = json.loads(out) if out else {}
    check("autonomic: regression blocks the stop with the failure named",
          blocked.get("decision") == "block" and "toggle" in blocked.get("reason", ""),
          out[:120])
    check("autonomic: debt survives a failed verify", (data / "state" / "dirty-a3.json").is_file())
    code, out = hook("verify_on_change.py",
                     {"session_id": "a3", "cwd": str(market), "stop_hook_active": True})
    check("autonomic: loop guard passes the second stop", code == 0 and out == "")

    code, out = hook("autonomic_brief.py", {"cwd": str(market)})
    context = (json.loads(out) if out else {}).get("hookSpecificOutput", {}).get("additionalContext", "")
    check("autonomic: brief surfaces the standing regression",
          "STANDING REGRESSION" in context and "toggle" in context)
    code, out = hook("autonomic_brief.py", {"cwd": str(market)},
                     {"CLAUDE_PLUGIN_DATA": str(tmp / "au-fresh")})
    check("autonomic: brief silent with no state", code == 0 and out == "")

    hook("change_sentinel.py", {**core_edit, "session_id": "ks"}, {"AGENTIC_OS_AUTONOMIC": "off"})
    check("autonomic: kill switch silences the reflexes",
          not (data / "state" / "dirty-ks.json").is_file())

    # pulse against the real repo tools with a planted trail: proposals get staged
    audit = tmp / "au-audit"
    audit.mkdir()
    lines = [json.dumps({"ts": f"2026-07-18T10:00:0{s}", "session": f"p{s}", "tool": "Bash",
                         "ok": False, "summary": "git-cliff not found"}) for s in range(4)]
    (audit / "trail.jsonl").write_text("\n".join(lines) + "\n")
    code, out = hook("evolution_pulse.py", {"session_id": "p", "cwd": str(ROOT)},
                     {"AGENTIC_OS_AUDIT_DIR": str(audit)})
    staged = data / "state" / "pending-proposals.json"
    payload = json.loads(staged.read_text()) if staged.is_file() else {}
    proposals = payload.get("proposals", [])
    check("autonomic: pulse stages mined proposals",
          any("git-cliff" in p["title"] for p in proposals), str([p.get("id") for p in proposals]))
    check("autonomic: pulse ranks the standing regression first",
          proposals and proposals[0]["kind"] == "fix" and "toggle" in proposals[0]["id"],
          proposals[0]["id"] if proposals else "none")


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_secret_guard()
        test_security_gate()
        test_commit_gate(tmp / "t1") if (tmp / "t1").mkdir(parents=True, exist_ok=True) or True else None
        test_trackers(tmp)
        test_manifest_validator(tmp)
        test_retrieval(tmp / "r") if (tmp / "r").mkdir(parents=True, exist_ok=True) or True else None
        test_doctor(tmp)
        test_self_evolution(tmp)
        test_long_horizon(tmp)
        test_autonomic_loop(tmp)

    total = len(PASSED) + len(FAILED)
    print(f"\n{'─' * 60}")
    if FAILED:
        print(f"{len(PASSED)}/{total} passed, {len(FAILED)} FAILED\n")
        for name, detail in FAILED:
            print(f"  {name}")
            if detail:
                print(f"      {detail}")
        return 1
    print(f"{total}/{total} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
