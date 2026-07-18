#!/usr/bin/env python3
"""PreToolUse gate: refuse to write a live credential into a file.

Scope note (ADR-0022). This gate used to carry three layers — path, bash and content. After
the merge that produced this repo, `core-guardrails/PreToolUse/20_security_gate.py` owns the
path and bash layers for the whole OS: it is always-enforcing, fails closed, honours
`/gate-unlock` and emits telemetry. Running two scanners over the same input produced two
denials for one mistake, two telemetry records for one event, and — worse — an override that
only half-worked, because this gate never honoured it.

What survives here is the layer the runtime gate does not have:

  content — never write a live credential into a file. Catches the case where a secret arrives
            from somewhere else (a paste, an API response, another file) and is about to be
            persisted.

Denies rather than exit-2 so the turn survives and Claude can route around the refusal.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import deny, proceed, read_event  # noqa: E402

# Live credential shapes. Deliberately narrow: a false positive here blocks real work, and a hook
# that cries wolf is a hook that gets switched off.
SECRET_CONTENT: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"sk-ant-(?:api|admin)\d{2}-[A-Za-z0-9_\-]{32,}"), "Anthropic API key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}"), "GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}"), "GitHub fine-grained PAT"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bASIA[0-9A-Z]{16}\b"), "AWS temporary access key id"),
    (re.compile(r"\bsk_live_[A-Za-z0-9]{24,}"), "Stripe live secret key"),
    (re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "Google API key"),
    (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"), "private key block"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "JWT"),
    (re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}"), "GitLab PAT"),
    (re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"), "npm token"),
)


def content_has_secret(text: str) -> str | None:
    for pattern, label in SECRET_CONTENT:
        if pattern.search(text):
            return label
    return None


def main() -> None:
    event = read_event()
    tool_input = event.get("tool_input") or {}

    payload = "\n".join(
        str(tool_input.get(key, ""))
        for key in ("content", "new_string", "command")
    )
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict):
            payload += "\n" + str(edit.get("new_string", ""))

    if payload.strip():
        label = content_has_secret(payload)
        if label:
            deny(
                f"secret-guard: refused — the content contains what looks like a live {label}.\n"
                f"Replace it with an environment variable reference (os.environ / ${{VAR}}) and "
                f"document the variable in the README instead of writing the value to disk."
            )

    proceed()


if __name__ == "__main__":
    main()
