#!/usr/bin/env python3
"""Structural and semantic validator for the agentic OS marketplace.

Checks every plugin, skill, agent, command, hook and decision record against the conventions the
loader will not tell you about: components misfiled under .claude-plugin/, version drift between
skill.json and SKILL.md frontmatter, dangling or superseded ADR references, non-executable hook
scripts, out-of-plugin path references.

Exit code 0 = clean, 1 = findings, 2 = usage error. Designed to be safe in CI and in a hook.

Usage:
    doctor.py                      # everything
    doctor.py --manifests          # plugin.json + marketplace.json only
    doctor.py --skills             # skills + version drift only
    doctor.py --adr                # decision record graph only
    doctor.py --hooks              # hook wiring only
    doctor.py --json               # machine-readable findings
    doctor.py --quiet              # exit code only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

SEMVER = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
COMPONENT_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ADR_REF = re.compile(r"^ADR-(\d{4})$")
ADR_FILE = re.compile(r"^(\d{4})-[a-z0-9]+(-[a-z0-9]+)*\.md$")
RANGE_OK = re.compile(r"^[\^~>=<]*\s*\d+\.\d+\.\d+")
VALID_LAYERS = {"L1-core", "L2-episodic", "L3-knowledge", "L4-index"}
VALID_STABILITY = {"experimental", "stable", "deprecated"}
VALID_STATUS = {"proposed", "accepted", "deprecated", "superseded"}
FORBIDDEN_AGENT_KEYS = {"hooks", "mcpServers", "permissionMode"}
COMPONENT_DIRS = ("skills", "agents", "commands", "hooks")


@dataclass
class Finding:
    level: str  # "error" | "warn"
    path: str
    message: str

    def render(self, root: Path) -> str:
        tag = "\033[31mERROR\033[0m" if self.level == "error" else "\033[33mWARN \033[0m"
        if not sys.stdout.isatty():
            tag = self.level.upper().ljust(5)
        try:
            shown = Path(self.path).relative_to(root)
        except ValueError:
            shown = Path(self.path)
        return f"  {tag}  {shown}\n         {self.message}"


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    checked: int = 0

    def error(self, path: Path | str, message: str) -> None:
        self.findings.append(Finding("error", str(path), message))

    def warn(self, path: Path | str, message: str) -> None:
        self.findings.append(Finding("warn", str(path), message))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "warn"]


def repo_root(start: Path | None = None) -> Path:
    """Walk up to the directory holding .claude-plugin/marketplace.json."""
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    print("doctor: not inside a marketplace (no .claude-plugin/marketplace.json)", file=sys.stderr)
    sys.exit(2)


def read_json(path: Path, report: Report) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.error(path, "file not found")
    except json.JSONDecodeError as exc:
        report.error(path, f"invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}")
    return None


def parse_frontmatter(path: Path, report: Report) -> dict | None:
    """Minimal YAML frontmatter reader.

    Handles the subset the conventions actually use: scalars, inline lists, and one level of
    nesting (metadata:). Avoids a PyYAML dependency so the validator runs anywhere python3 does.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        report.error(path, "file not found")
        return None

    if not text.startswith("---"):
        report.error(path, "missing YAML frontmatter (file must start with ---)")
        return None

    end = text.find("\n---", 3)
    if end == -1:
        report.error(path, "unterminated YAML frontmatter (no closing ---)")
        return None

    block = text[3:end]
    data: dict = {}
    current_parent: str | None = None

    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indented = raw[0] in (" ", "\t")
        line = raw.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()

        if indented and current_parent:
            data.setdefault(current_parent, {})
            if isinstance(data[current_parent], dict):
                data[current_parent][key] = _coerce(value)
            continue

        if value == "":
            data[key] = {}
            current_parent = key
        else:
            data[key] = _coerce(value)
            current_parent = None
    return data


def _coerce(value: str):
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [v.strip().strip("'\"") for v in inner.split(",")]
    return value.strip("'\"")


def check_marketplace(root: Path, report: Report) -> list[Path]:
    path = root / ".claude-plugin" / "marketplace.json"
    data = read_json(path, report)
    if data is None:
        return []
    report.checked += 1

    if not data.get("name"):
        report.error(path, "marketplace requires a 'name'")

    plugin_dirs: list[Path] = []
    seen: set[str] = set()
    for entry in data.get("plugins", []):
        name = entry.get("name")
        if not name:
            report.error(path, "plugin entry without a 'name'")
            continue
        if name in seen:
            report.error(path, f"duplicate plugin entry '{name}'")
        seen.add(name)

        if "version" in entry:
            report.error(
                path,
                f"'{name}' sets 'version' in the marketplace entry; plugin.json wins silently and "
                "this value becomes a lie. Remove it.",
            )

        source = entry.get("source")
        if not isinstance(source, str):
            report.error(path, f"'{name}' has a non-string 'source'; only local sources are checked")
            continue

        pdir = (root / source).resolve()
        if not pdir.is_dir():
            report.error(path, f"'{name}' points at a missing directory: {source}")
            continue
        if not (pdir / ".claude-plugin" / "plugin.json").is_file():
            report.error(path, f"'{name}' has no .claude-plugin/plugin.json at {source}")
            continue
        plugin_dirs.append(pdir)

    on_disk = {p.name for p in (root / "plugins").iterdir() if p.is_dir()} if (root / "plugins").is_dir() else set()
    for orphan in sorted(on_disk - seen):
        report.warn(root / "plugins" / orphan, "plugin directory is not listed in marketplace.json")

    return plugin_dirs


def check_plugin(pdir: Path, report: Report) -> dict:
    manifest_path = pdir / ".claude-plugin" / "plugin.json"
    manifest = read_json(manifest_path, report) or {}
    report.checked += 1

    name = manifest.get("name")
    if not name:
        report.error(manifest_path, "'name' is the only required field and it is missing")
    elif not COMPONENT_NAME.match(name):
        report.error(manifest_path, f"name '{name}' must be lower-case kebab-case")
    elif name != pdir.name:
        report.error(manifest_path, f"name '{name}' does not match directory '{pdir.name}'")

    version = manifest.get("version")
    if version is None:
        report.warn(
            manifest_path,
            "no 'version'; the loader falls back to the commit SHA, so installs update silently "
            "and cannot be pinned by tag",
        )
    elif not SEMVER.match(str(version)):
        report.error(manifest_path, f"version '{version}' is not valid SemVer")

    if not manifest.get("description"):
        report.warn(manifest_path, "no 'description'; it is what users see in /plugin")

    for dep, rng in (manifest.get("dependencies") or {}).items():
        if not isinstance(rng, str) or not RANGE_OK.match(rng.strip()):
            report.error(manifest_path, f"dependency '{dep}' has an unparseable range: {rng!r}")

    # Components misfiled under .claude-plugin/ — loads clean, does nothing.
    for comp in COMPONENT_DIRS:
        stray = pdir / ".claude-plugin" / comp
        if stray.exists():
            report.error(
                stray,
                f"'{comp}/' must sit at the plugin root, not inside .claude-plugin/. "
                "The plugin will load without error and silently expose nothing.",
            )
    if (pdir / "CLAUDE.md").is_file():
        report.warn(pdir / "CLAUDE.md", "plugin-level CLAUDE.md is ignored by the loader; ship instructions as a skill")

    return manifest


def check_skill(sdir: Path, report: Report) -> None:
    skill_md = sdir / "SKILL.md"
    if not skill_md.is_file():
        report.error(sdir, "skill directory without SKILL.md")
        return
    report.checked += 1

    fm = parse_frontmatter(skill_md, report)
    if fm is None:
        return

    name = fm.get("name")
    if not name:
        report.error(skill_md, "frontmatter requires 'name'")
    elif not COMPONENT_NAME.match(str(name)):
        report.error(skill_md, f"name '{name}' must be lower-case kebab-case")
    elif name != sdir.name:
        report.error(skill_md, f"name '{name}' does not match directory '{sdir.name}'")

    desc = str(fm.get("description") or "")
    if not desc:
        report.error(skill_md, "frontmatter requires 'description' — it is the entire trigger surface")
    elif len(desc) < 80:
        report.warn(
            skill_md,
            f"description is {len(desc)} chars; short descriptions undertrigger. Enumerate the "
            "phrasings and situations that should fire this skill.",
        )

    body_lines = skill_md.read_text(encoding="utf-8").count("\n")
    if body_lines > 500:
        report.warn(skill_md, f"{body_lines} lines; push detail into reference/ with a pointer (target <500)")

    meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
    fm_version = meta.get("version")
    layer = meta.get("layer")
    if layer and layer not in VALID_LAYERS:
        report.error(skill_md, f"metadata.layer '{layer}' not in {sorted(VALID_LAYERS)}")

    manifest_path = sdir / "skill.json"
    if not manifest_path.is_file():
        report.warn(manifest_path, "no skill.json; per-skill version, dependencies and ADR links are unavailable")
        return

    manifest = read_json(manifest_path, report)
    if manifest is None:
        return

    if manifest.get("name") != sdir.name:
        report.error(manifest_path, f"name '{manifest.get('name')}' does not match directory '{sdir.name}'")

    version = manifest.get("version")
    if not version or not SEMVER.match(str(version)):
        report.error(manifest_path, f"version '{version}' is not valid SemVer")
    elif fm_version and str(fm_version) != str(version):
        report.error(
            manifest_path,
            f"version drift: skill.json says {version}, SKILL.md metadata.version says {fm_version}",
        )
    elif not fm_version:
        report.warn(skill_md, f"skill.json declares {version} but frontmatter has no metadata.version")

    if manifest.get("layer") and manifest["layer"] not in VALID_LAYERS:
        report.error(manifest_path, f"layer '{manifest['layer']}' not in {sorted(VALID_LAYERS)}")
    if manifest.get("stability") and manifest["stability"] not in VALID_STABILITY:
        report.error(manifest_path, f"stability '{manifest['stability']}' not in {sorted(VALID_STABILITY)}")

    for dep, rng in (manifest.get("dependencies") or {}).items():
        if not isinstance(rng, str) or not RANGE_OK.match(rng.strip()):
            report.error(manifest_path, f"dependency '{dep}' has an unparseable range: {rng!r}")

    for ref in manifest.get("adr") or []:
        if not ADR_REF.match(str(ref)):
            report.error(manifest_path, f"malformed ADR reference '{ref}' (expected ADR-NNNN)")


def check_agent(path: Path, report: Report) -> None:
    report.checked += 1
    fm = parse_frontmatter(path, report)
    if fm is None:
        return

    name = fm.get("name")
    if not name:
        report.error(path, "agent frontmatter requires 'name'")
    elif name != path.stem:
        report.error(path, f"name '{name}' does not match filename '{path.stem}'")

    if not fm.get("description"):
        report.error(path, "agent frontmatter requires 'description' — it is how the orchestrator decides to delegate")

    for key in FORBIDDEN_AGENT_KEYS:
        if key in fm:
            report.error(path, f"plugin-shipped agents may not declare '{key}'; the loader rejects it")


def check_hooks(pdir: Path, report: Report) -> None:
    hooks_json = pdir / "hooks" / "hooks.json"
    if not hooks_json.is_file():
        return
    report.checked += 1

    data = read_json(hooks_json, report)
    if data is None:
        return

    if "hooks" not in data:
        report.error(
            hooks_json,
            "plugin hook config must wrap events in a top-level {\"hooks\": {...}} object; the "
            "bare settings.json shape is silently ignored here",
        )
        return

    for event, matchers in data["hooks"].items():
        if not isinstance(matchers, list):
            report.error(hooks_json, f"event '{event}' must map to a list of matcher objects")
            continue
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                cmd = hook.get("command", "")
                if "${CLAUDE_PLUGIN_ROOT}" not in cmd and not cmd.startswith("$"):
                    report.warn(hooks_json, f"{event}: command does not use ${{CLAUDE_PLUGIN_ROOT}}: {cmd[:60]}")
                for token in cmd.split():
                    if "${CLAUDE_PLUGIN_ROOT}" not in token:
                        continue
                    rel = token.replace("${CLAUDE_PLUGIN_ROOT}/", "").strip("\"'")
                    target = pdir / rel
                    if not target.exists():
                        report.error(hooks_json, f"{event}: command points at a missing file: {rel}")
                    elif not os.access(target, os.X_OK):
                        report.error(target, "hook script is not executable (chmod +x)")


def check_adr_graph(root: Path, report: Report, manifest_refs: set[str]) -> None:
    adr_dir = root / "adr"
    if not adr_dir.is_dir():
        if manifest_refs:
            report.error(adr_dir, f"manifests reference {len(manifest_refs)} ADRs but adr/ does not exist")
        return

    records: dict[str, dict] = {}
    for path in sorted(adr_dir.glob("*.md")):
        if path.name in {"README.md", "template.md"}:
            continue
        report.checked += 1
        if not ADR_FILE.match(path.name):
            report.error(path, "filename must be NNNN-kebab-title.md")
            continue
        number = path.name[:4]
        fm = parse_frontmatter(path, report)
        if fm is None:
            continue
        status = fm.get("status")
        if status not in VALID_STATUS:
            report.error(path, f"status '{status}' not in {sorted(VALID_STATUS)}")
        records[number] = {"path": path, "fm": fm, "status": status}

    for number, rec in records.items():
        for target in _as_list(rec["fm"].get("superseded-by")):
            t = str(target).zfill(4)
            if t not in records:
                report.error(rec["path"], f"superseded-by points at non-existent ADR-{t}")
            elif number not in {str(x).zfill(4) for x in _as_list(records[t]["fm"].get("supersedes"))}:
                report.error(rec["path"], f"ADR-{t} does not declare 'supersedes: [{number}]' — chain is one-sided")
            elif rec["status"] != "superseded":
                report.error(rec["path"], f"has superseded-by ADR-{t} but status is '{rec['status']}'")

        for target in _as_list(rec["fm"].get("supersedes")):
            t = str(target).zfill(4)
            if t not in records:
                report.error(rec["path"], f"supersedes points at non-existent ADR-{t}")

    for ref in sorted(manifest_refs):
        number = ref.split("-")[1]
        if number not in records:
            report.error(root, f"manifest references {ref} but no such decision record exists")
        elif records[number]["status"] == "superseded":
            report.warn(root, f"manifest references {ref} which is superseded; point it at the successor")

    for number, rec in records.items():
        if rec["status"] == "proposed":
            report.warn(rec["path"], "status is 'proposed' — accept it or delete it; open decisions are debt")


def _as_list(value) -> list:
    if value is None or value == "":
        return []
    return value if isinstance(value, list) else [value]


def collect_adr_refs(root: Path) -> set[str]:
    refs: set[str] = set()
    for manifest in root.glob("plugins/*/skills/*/skill.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for ref in data.get("adr") or []:
            if ADR_REF.match(str(ref)):
                refs.add(str(ref))
    return refs


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the agentic OS marketplace.")
    parser.add_argument("--manifests", action="store_true", help="plugin.json + marketplace.json only")
    parser.add_argument("--skills", action="store_true", help="skills and version drift only")
    parser.add_argument("--adr", action="store_true", help="decision record graph only")
    parser.add_argument("--hooks", action="store_true", help="hook wiring only")
    parser.add_argument("--json", action="store_true", help="machine-readable findings")
    parser.add_argument("--quiet", "-q", action="store_true", help="exit code only")
    parser.add_argument("--root", type=Path, default=None, help="marketplace root (default: auto-detect)")
    args = parser.parse_args()

    selective = args.manifests or args.skills or args.adr or args.hooks
    run_manifests = args.manifests or not selective
    run_skills = args.skills or not selective
    run_adr = args.adr or not selective
    run_hooks = args.hooks or not selective

    root = args.root.resolve() if args.root else repo_root()
    report = Report()

    plugin_dirs = check_marketplace(root, report)

    for pdir in plugin_dirs:
        if run_manifests:
            check_plugin(pdir, report)
        if run_skills:
            for sdir in sorted((pdir / "skills").iterdir()) if (pdir / "skills").is_dir() else []:
                if sdir.is_dir():
                    check_skill(sdir, report)
            for apath in sorted((pdir / "agents").glob("*.md")) if (pdir / "agents").is_dir() else []:
                check_agent(apath, report)
        if run_hooks:
            check_hooks(pdir, report)

    if run_adr:
        check_adr_graph(root, report, collect_adr_refs(root))

    if args.json:
        print(json.dumps(
            {
                "checked": report.checked,
                "errors": [{"path": f.path, "message": f.message} for f in report.errors],
                "warnings": [{"path": f.path, "message": f.message} for f in report.warnings],
            },
            indent=2,
        ))
        return 1 if report.errors else 0

    if not args.quiet:
        if report.findings:
            print(f"\ndoctor: {report.checked} components checked\n")
            for finding in report.findings:
                print(finding.render(root))
            print(f"\n{len(report.errors)} error(s), {len(report.warnings)} warning(s)\n")
        else:
            print(f"doctor: {report.checked} components checked — clean")

    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
