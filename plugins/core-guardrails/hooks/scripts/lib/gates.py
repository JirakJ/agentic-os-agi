"""Gate mode resolution: enforce | dryrun | off.

Precedence: env JJ_GATE_<NAME> > ~/.jj-agentic-os/gates.json > plugin default gates.json.
Dry-run gates log telemetry and emit an advisory instead of blocking - the promotion model
(promote to enforce once measured FP < 2%) from the guardrail-forge skill.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from lib import cc

_DEFAULTS_FILE = Path(__file__).resolve().parent.parent / "gates.json"

def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def mode(gate: str) -> str:
    env = os.environ.get("JJ_GATE_" + gate.replace("-", "_").upper())
    if env in ("enforce", "dryrun", "off"):
        return env
    user = _load(cc.home_dir() / "gates.json").get(gate, {})
    if user.get("mode") in ("enforce", "dryrun", "off"):
        return user["mode"]
    dflt = _load(_DEFAULTS_FILE).get(gate, {})
    return dflt.get("mode", "dryrun")

def enforcing(gate: str) -> bool:
    return mode(gate) == "enforce"

def active(gate: str) -> bool:
    return mode(gate) != "off"
