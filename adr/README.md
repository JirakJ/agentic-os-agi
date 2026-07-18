# Architecture Decision Records

MADR 4.0.0 records for the agentic OS. These document *why* the fleet behaves the way it does — Git
shows what changed, these show what was traded away.

## Index

```bash
python3 ../plugins/core-orchestration/scripts/adr_new.py --list
```

## Adding one

```bash
python3 ../plugins/core-orchestration/scripts/adr_new.py "Short present-tense title"
```

The record lands before the code it justifies, in its own `docs(adr):` commit. Accepted records are
immutable — supersede rather than edit:

```bash
python3 ../plugins/core-orchestration/scripts/adr_new.py "New decision" --supersedes 0007
```

The full workflow, including what belongs in each section, is in the `adr-workflow` skill.

## Status lifecycle

```
proposed ──accept──▶ accepted ──▶ deprecated
                        │
                        └──superseded by ADR-NNNN──▶ superseded
```

`proposed` records are debt. Accept them or delete them.
