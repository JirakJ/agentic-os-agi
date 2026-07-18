# Agentic OS — marketplace maintenance.
# Everything here is also runnable directly; the targets exist so the common path is one word.

PY      := python3
SCRIPTS := plugins/core-orchestration/scripts
MEMORY  := plugins/memory-obsidian/scripts
EVOLVE  := plugins/self-evolution/scripts
HORIZON := plugins/long-horizon/scripts

.PHONY: help doctor test adr release status index recall evals evolve missions frontier install clean

help:
	@echo "doctor    validate every plugin, skill, agent, hook and decision record"
	@echo "test      run the hook and retrieval test suite against real payloads"
	@echo "status    version / tag / pin drift across all plugins"
	@echo "adr       create a decision record        (make adr T='Title')"
	@echo "release   cut a release                   (make release P=plugin B=minor)"
	@echo "index     refresh the retrieval index     (make index V=~/Vault)"
	@echo "recall    query the index                 (make recall Q='query')"
	@echo "evals     run the capability-eval suite, report regression vs baseline"
	@echo "evolve    mine experience, generate ranked capability proposals"
	@echo "missions  list missions in flight (goal state that outlives sessions)"
	@echo "frontier  the self-model + what the system should learn next"
	@echo "install   register this marketplace with Claude Code"
	@echo "clean     drop derived caches"

doctor:
	@$(PY) $(SCRIPTS)/doctor.py

test:
	@$(PY) tests/run_tests.py

status:
	@$(PY) $(SCRIPTS)/release.py --status

adr:
	@test -n "$(T)" || { echo "usage: make adr T='Short title'"; exit 2; }
	@$(PY) $(SCRIPTS)/adr_new.py "$(T)"

release:
	@test -n "$(P)" || { echo "usage: make release P=<plugin> [B=major|minor|patch]"; exit 2; }
	@$(PY) $(SCRIPTS)/release.py $(P) $(if $(B),--bump $(B),) --dry-run
	@echo ""
	@read -p "proceed? [y/N] " ok; [ "$$ok" = "y" ] || exit 1
	@$(PY) $(SCRIPTS)/release.py $(P) $(if $(B),--bump $(B),)

index:
	@$(PY) $(MEMORY)/index_vault.py $(if $(V),--vault $(V),) --memory ./memory

recall:
	@test -n "$(Q)" || { echo "usage: make recall Q='what did I decide about X'"; exit 2; }
	@$(PY) $(MEMORY)/recall.py "$(Q)"

evals:
	@$(PY) $(EVOLVE)/evalctl.py $(if $(E),--eval $(E),)

evolve:
	@$(PY) $(EVOLVE)/propose.py $(if $(N),--top $(N),)

missions:
	@$(PY) $(HORIZON)/mission.py list

frontier:
	@$(PY) $(HORIZON)/frontier.py

install:
	@claude plugin marketplace add .
	@echo "now: /plugin install core-orchestration@agentic-os"

clean:
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -f /tmp/vectest.db
	@echo "derived caches dropped (the index lives in CLAUDE_PLUGIN_DATA and is rebuildable)"
