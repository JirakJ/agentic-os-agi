#!/usr/bin/env python3
"""PreToolUse gate: refuse to read, write or exfiltrate secrets.

Two layers, because they fail differently:

  path  — never open a credential file. Cheap, exact, catches the common case.
  content — never write a live credential into a tracked file. Catches the case where a secret
            arrives from somewhere else and is about to be committed.

Both deny rather than exit-2 so the turn survives and Claude can route around the refusal.
Example files (.env.example, .env.sample, .env.template) are explicitly allowed — they are
documentation, and blocking them trains you to disable the hook.
"""

from __future__ import annotations

import re
import sys
from fnmatch import fnmatch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import deny, proceed, read_event, tool_paths  # noqa: E402

SECRET_PATHS: tuple[str, ...] = (
    "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore", "*.jks",
    "*/.env", ".env", "*.env", "*/.env.*",
    "*/id_rsa", "*/id_ed25519", "*/id_ecdsa", "*/id_dsa",
    "*/.ssh/*", "*/.aws/credentials", "*/.aws/config",
    "*/.npmrc", "*/.pypirc", "*/.netrc", "*/.git-credentials",
    "*/.docker/config.json", "*/.kube/config",
    "*secrets.y*ml", "*credentials.json", "*service-account*.json",
    "*/.claude/settings.local.json",
)

ALLOWED_PATHS: tuple[str, ...] = (
    "*.env.example", "*.env.sample", "*.env.template", "*.env.dist",
    "*/env.d.ts", "*secrets.example.y*ml",
)

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

# Bash that reads a secret file or ships the environment somewhere.
DANGEROUS_BASH: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\b(?:cat|less|more|head|tail|bat|xxd|od|strings)\s+[^|;&]*(?:/\.env\b|\.pem\b|/\.ssh/|id_rsa|\.aws/credentials|\.git-credentials)"),
     "reads a credential file"),
    (re.compile(r"\b(?:curl|wget|nc|ncat)\b[^|;&]*(?:\$[A-Z_]*(?:TOKEN|KEY|SECRET|PASSWORD)|\.env\b)"),
     "sends a credential to the network"),
    (re.compile(r"\b(?:env|printenv|set)\s*(?:\||>)"), "pipes the environment somewhere"),
    (re.compile(r"\bgit\s+config\s+(?:--global\s+)?(?:user\.|credential\.)"), "rewrites git credentials"),
)


def path_is_secret(raw: str) -> str | None:
    candidate = str(Path(raw).expanduser())
    if any(fnmatch(candidate, allowed) for allowed in ALLOWED_PATHS):
        return None
    for pattern in SECRET_PATHS:
        if fnmatch(candidate, pattern) or fnmatch(Path(candidate).name, pattern.lstrip("*/")):
            return pattern
    return None


def content_has_secret(text: str) -> str | None:
    for pattern, label in SECRET_CONTENT:
        if pattern.search(text):
            return label
    return None


def main() -> None:
    event = read_event()
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}

    if tool == "Bash":
        command = tool_input.get("command", "")
        for pattern, why in DANGEROUS_BASH:
            if pattern.search(command):
                deny(
                    f"secret-guard: refused — this command {why}.\n"
                    f"If you need the value, ask the user to supply it, or read it from the "
                    f"environment at runtime rather than printing it into the transcript."
                )
        proceed()

    for raw in tool_paths(event):
        hit = path_is_secret(raw)
        if hit:
            deny(
                f"secret-guard: refused — '{Path(raw).name}' matches a credential path ({hit}).\n"
                f"Credentials never enter the transcript. Reference them via environment "
                f"variables, or ask the user to paste only the specific value you need."
            )

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
