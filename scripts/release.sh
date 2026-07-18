#!/usr/bin/env bash
# Lockstep release: bump VERSION + all plugin.json + marketplace.json + CHANGELOG atomically,
# regenerate adapters, run preflight, tag. Usage: scripts/release.sh 3.1.0 "Release title"
set -euo pipefail
NEW="${1:?usage: release.sh <semver> [title]}"
TITLE="${2:-Release $NEW}"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
echo "$NEW" > VERSION
python3 - "$NEW" <<'PYEOF'
import json, pathlib, sys
new = sys.argv[1]
mp = pathlib.Path(".claude-plugin/marketplace.json")
data = json.loads(mp.read_text())
data.setdefault("metadata", {})["version"] = new
for p in data.get("plugins", []):
    p["version"] = new
    pj = pathlib.Path("plugins") / p["name"] / ".claude-plugin" / "plugin.json"
    pd = json.loads(pj.read_text())
    pd["version"] = new
    pj.write_text(json.dumps(pd, indent=2) + "\n")
mp.write_text(json.dumps(data, indent=2) + "\n")
pyproject = pathlib.Path("pyproject.toml")
t = pyproject.read_text().splitlines()
pyproject.write_text("\n".join(
    f'version = "{new}"' if l.startswith('version = "') else l for l in t) + "\n")
PYEOF
DATE="$(date -u +%Y-%m-%d)"
python3 - "$NEW" "$DATE" "$TITLE" <<'PYEOF'
import pathlib, sys
new, date, title = sys.argv[1:4]
ch = pathlib.Path("CHANGELOG.md")
text = ch.read_text()
if f"[{new}]" not in text:
    marker = "\n## ["
    idx = text.find(marker)
    entry = f"\n## [{new}] - {date}\n### Changed\n- {title}\n"
    text = text[:idx] + entry + text[idx:] if idx > 0 else text + entry
    ch.write_text(text)
PYEOF
python3 scripts/build-adapters.py
bash scripts/preflight.sh
git add -A
git commit -m "chore(release): v$NEW - $TITLE"
git tag -a "v$NEW" -m "$TITLE"
echo "release: v$NEW committed and tagged. Push with: git push --follow-tags"
