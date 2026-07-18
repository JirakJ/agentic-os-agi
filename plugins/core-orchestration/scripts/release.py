#!/usr/bin/env python3
"""Cut and roll back versioned releases of marketplace plugins.

A release is: derive the bump from Conventional Commits, write plugin.json, regenerate the scoped
changelog, commit, tag <plugin>/vX.Y.Z, then re-pin the marketplace entry's sha to the tagged
commit. A rollback is just the last step pointed at an older tag.

Usage:
    release.py <plugin> --dry-run              # read the plan, touch nothing
    release.py <plugin>                        # bump derived from commits
    release.py <plugin> --bump minor
    release.py <plugin> --pin v1.1.0           # roll back: re-pin only
    release.py --status                        # every plugin: version, tag, pin, drift
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$")
CONVENTIONAL = re.compile(r"^(?P<type>\w+)(?:\((?P<scope>[^)]*)\))?(?P<breaking>!)?:\s*(?P<subject>.+)$")
MINOR_TYPES = {"feat"}
PATCH_TYPES = {"fix", "perf", "refactor", "revert"}


class Fail(Exception):
    pass


def run(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise Fail(f"{' '.join(args)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    raise Fail("not inside a marketplace (no .claude-plugin/marketplace.json)")


def bump_version(version: str, level: str) -> str:
    match = SEMVER.match(version)
    if not match:
        raise Fail(f"'{version}' is not valid SemVer")
    major, minor, patch = (int(match.group(i)) for i in (1, 2, 3))
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def last_tag(root: Path, plugin: str) -> str | None:
    tags = run("git", "tag", "--list", f"{plugin}/v*", "--sort=-v:refname", cwd=root, check=False)
    return tags.splitlines()[0] if tags else None


def commits_since(root: Path, plugin: str, tag: str | None) -> list[str]:
    span = f"{tag}..HEAD" if tag else "HEAD"
    out = run("git", "log", span, "--pretty=%s%n%b%x00", "--", f"plugins/{plugin}/", cwd=root, check=False)
    return [c.strip() for c in out.split("\x00") if c.strip()]


def derive_bump(commits: list[str]) -> tuple[str, str]:
    """Return (level, why). Breaking beats feat beats fix; unparseable commits force patch."""
    level, why = None, ""
    for commit in commits:
        subject = commit.splitlines()[0]
        match = CONVENTIONAL.match(subject)
        if not match:
            continue
        if match.group("breaking") or "BREAKING CHANGE:" in commit:
            return "major", f"breaking change: {subject}"
        ctype = match.group("type")
        if ctype in MINOR_TYPES and level != "minor":
            level, why = "minor", f"new capability: {subject}"
        elif ctype in PATCH_TYPES and level is None:
            level, why = "patch", f"fix: {subject}"
    if level is None:
        return "patch", "no feat/fix commits found — defaulting to patch"
    return level, why


def marketplace_entry(root: Path, plugin: str) -> tuple[dict, dict, Path]:
    path = root / ".claude-plugin" / "marketplace.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data.get("plugins", []):
        if entry.get("name") == plugin:
            return data, entry, path
    raise Fail(f"'{plugin}' is not listed in marketplace.json")


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def changelog(root: Path, plugin: str, version: str, dry_run: bool) -> bool:
    if not shutil.which("git-cliff"):
        print("  ! git-cliff not on PATH — skipping changelog (brew install git-cliff)")
        return False
    target = root / "plugins" / plugin / "CHANGELOG.md"
    cmd = ["git-cliff", "--include-path", f"plugins/{plugin}/**", "--tag", f"{plugin}/v{version}",
           "--config", str(root / "cliff.toml"), "--output", str(target)]
    if dry_run:
        print(f"  would run: {' '.join(cmd)}")
        return True
    run(*cmd, cwd=root)
    return True


def cmd_status(root: Path) -> int:
    data = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    print(f"{'plugin':<24} {'version':<10} {'tag':<12} {'pinned sha':<12} drift")
    print("-" * 72)
    rc = 0
    for entry in data.get("plugins", []):
        plugin = entry["name"]
        manifest = root / entry["source"] / ".claude-plugin" / "plugin.json"
        version = json.loads(manifest.read_text(encoding="utf-8")).get("version", "—")
        tag = last_tag(root, plugin) or "—"
        pinned = (entry.get("sha") or "—")[:10]
        tag_version = tag.split("/v")[-1] if "/v" in tag else None

        drift = "ok"
        if tag_version and tag_version != version:
            drift = f"manifest {version} ≠ tag {tag_version}"
            rc = 1
        elif entry.get("sha"):
            tag_sha = run("git", "rev-parse", f"{tag}^{{commit}}", cwd=root, check=False) if tag != "—" else ""
            if tag_sha and not tag_sha.startswith(entry["sha"][:10]):
                drift = "pin ≠ tag"
                rc = 1
        elif tag != "—":
            drift = "unpinned"
        print(f"{plugin:<24} {version:<10} {tag.split('/')[-1]:<12} {pinned:<12} {drift}")
    return rc


def cmd_pin(root: Path, plugin: str, tag_name: str, dry_run: bool) -> int:
    full_tag = tag_name if "/" in tag_name else f"{plugin}/{tag_name}"
    sha = run("git", "rev-parse", f"{full_tag}^{{commit}}", cwd=root, check=False)
    if not sha:
        raise Fail(f"tag '{full_tag}' does not exist — `git tag --list '{plugin}/v*'`")

    data, entry, path = marketplace_entry(root, plugin)
    before = entry.get("sha", "—")
    print(f"re-pin {plugin}: {before[:10]} → {sha[:10]} ({full_tag})")
    if dry_run:
        print("  dry run — nothing written")
        return 0

    entry["ref"] = full_tag.split("/", 1)[1]
    entry["sha"] = sha
    write_json(path, data)
    run("git", "add", str(path.relative_to(root)), cwd=root)
    run("git", "commit", "-m", f"chore(marketplace): pin {plugin} to {full_tag.split('/', 1)[1]}", cwd=root)
    print(f"  committed. Push to move consumers: git push")
    return 0


def cmd_release(root: Path, plugin: str, level: str | None, dry_run: bool) -> int:
    manifest_path = root / "plugins" / plugin / ".claude-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise Fail(f"no manifest at {manifest_path.relative_to(root)}")

    dirty = run("git", "status", "--porcelain", cwd=root, check=False)
    if dirty and not dry_run:
        raise Fail("working tree is dirty — a release cut over uncommitted work is unreproducible:\n" + dirty)

    doctor = root / "plugins" / "core-orchestration" / "scripts" / "doctor.py"
    if doctor.is_file():
        result = subprocess.run([sys.executable, str(doctor), "--quiet"], cwd=root)
        if result.returncode != 0:
            raise Fail("doctor.py reports errors — fix them before releasing (run it without --quiet)")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    current = manifest.get("version")
    if not current:
        raise Fail(f"{plugin} has no 'version' in plugin.json — set one before the first release")

    tag = last_tag(root, plugin)
    commits = commits_since(root, plugin, tag)
    if not commits and not dry_run:
        raise Fail(f"no commits touching plugins/{plugin}/ since {tag or 'the beginning'} — nothing to release")

    if level:
        why = f"--bump {level}"
    else:
        level, why = derive_bump(commits)
    new_version = bump_version(current, level)
    new_tag = f"{plugin}/v{new_version}"

    print(f"\nrelease plan: {plugin}")
    print(f"  since      {tag or '(no previous tag)'} — {len(commits)} commit(s)")
    print(f"  bump       {current} → {new_version} ({level})")
    print(f"  because    {why}")
    print(f"  tag        {new_tag}")
    for commit in commits[:10]:
        print(f"    · {commit.splitlines()[0]}")
    if len(commits) > 10:
        print(f"    … and {len(commits) - 10} more")

    if dry_run:
        print("\n  dry run — nothing written\n")
        return 0

    manifest["version"] = new_version
    write_json(manifest_path, manifest)
    run("git", "add", str(manifest_path.relative_to(root)), cwd=root)

    if changelog(root, plugin, new_version, dry_run=False):
        cl = root / "plugins" / plugin / "CHANGELOG.md"
        if cl.is_file():
            run("git", "add", str(cl.relative_to(root)), cwd=root)

    run("git", "commit", "-m", f"chore(manifest/{plugin}): release v{new_version}", cwd=root)
    run("git", "tag", "-a", new_tag, "-m", f"{plugin} v{new_version}", cwd=root)
    sha = run("git", "rev-parse", "HEAD", cwd=root)

    data, entry, mpath = marketplace_entry(root, plugin)
    entry["ref"] = f"v{new_version}"
    entry["sha"] = sha
    write_json(mpath, data)
    run("git", "add", str(mpath.relative_to(root)), cwd=root)
    run("git", "commit", "-m", f"chore(marketplace): pin {plugin} to v{new_version}", cwd=root)

    print(f"\n  tagged {new_tag} @ {sha[:10]}, marketplace re-pinned")
    print(f"  push to publish:  git push origin HEAD --follow-tags\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cut and roll back marketplace plugin releases.")
    parser.add_argument("plugin", nargs="?", help="plugin name as listed in marketplace.json")
    parser.add_argument("--bump", choices=["major", "minor", "patch"], help="override the derived level")
    parser.add_argument("--pin", metavar="TAG", help="roll back: re-pin the marketplace entry to an existing tag")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    parser.add_argument("--status", action="store_true", help="version/tag/pin drift across all plugins")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()

    try:
        root = args.root.resolve() if args.root else repo_root()
        if args.status:
            return cmd_status(root)
        if not args.plugin:
            parser.error("a plugin name is required (or use --status)")
        if args.pin:
            return cmd_pin(root, args.plugin, args.pin, args.dry_run)
        return cmd_release(root, args.plugin, args.bump, args.dry_run)
    except Fail as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
