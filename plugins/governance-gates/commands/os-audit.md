---
description: Summarise the governance audit trail — what the fleet did, to which components
argument-hint: "[YYYY-MM-DD]"
---

```bash
DAY="${1:-$(date +%F)}"
TRAIL="${CLAUDE_PLUGIN_DATA}/audit/${DAY}.jsonl"
test -f "$TRAIL" || { echo "no trail for $DAY"; ls "${CLAUDE_PLUGIN_DATA}/audit/" 2>/dev/null; exit 0; }

python3 - "$TRAIL" <<'PY'
import json, sys
from collections import Counter

tools, components, failures, sessions = Counter(), Counter(), [], set()
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        continue
    tools[record.get("tool", "?")] += 1
    sessions.add(record.get("session"))
    for component in record.get("components", []):
        components[component] += 1
    if not record.get("ok", True):
        failures.append(record)

print(f"{sum(tools.values())} calls across {len(sessions)} session(s)\n")
print("tools:")
for tool, n in tools.most_common(8):
    print(f"  {n:5}  {tool}")
if components:
    print("\ncore components touched:")
    for component, n in components.most_common(12):
        print(f"  {n:5}  {component}")
if failures:
    print(f"\n{len(failures)} failed call(s):")
    for record in failures[:10]:
        print(f"  {record['ts']}  {record['tool']}  {record.get('summary', '')[:60]}")
PY
```

Report the shape of the day: which components saw churn, and whether anything failed repeatedly. A
component touched many times across many sessions without a matching commit run is a sign the
commit gate is being worked around.

The trail records actions, never payloads — file contents and command output are deliberately
absent, because a trail full of payloads is a second copy of your secrets.
