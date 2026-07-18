# Runbook: a gate blocked something it should not have
1. Read the deny reason; confirm which gate fired (`/gate-status`, telemetry queue).
2. Unblock NOW if needed: user runs `/gate-unlock` (10-min TTL, logged) and retries.
3. Fix properly via guardrail-forge: reproduce from the telemetry record, tune
   allowlist.json pattern or add an exemption, add a must-allow fixture, run
   `bash scripts/hook-dryrun-harness.sh` + pytest.
4. If the gate is enforcing and FP proxy rises to >= 2%, demote to dryrun in
   ~/.jj-agentic-os/gates.json until tuned. Log a 30-retros/ vault note (route: guardrail-forge).
