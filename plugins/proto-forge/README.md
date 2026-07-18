# proto-forge (plugin)

Distributable shell for the `proto-forge` skill (BRS-PROTO-FORGE-001 v1.1.0 §17.1). The
plugin contains no engine logic beyond the vendored skill itself; the skill under
`skills/proto-forge/` IS the engine, vendored at a pinned version.

## Layering & lockstep

- Canonical development copy: `~/.claude/skills/proto-forge` (author's machine).
- A skill release drives the matching plugin release: sync, bump, tag.

Release ritual (from repo root):

```sh
rsync -a --delete --exclude plugin --exclude .DS_Store \
  ~/.claude/skills/proto-forge/ plugins/proto-forge/skills/proto-forge/
make release PLUGIN=proto-forge VERSION=X.Y.Z
# then pin the new sha in .claude-plugin/marketplace.json (Makefile prints it)
```

## Seed provenance (BRS §17.2)

`skills/proto-forge/template/.proto-forge/seed.lock` pins the vendored `@jj/proto-ui`
tree by sha256; the generated app's `snapshot:diff` gate re-verifies the checksum every
run. `seed.lock.sha` records the agentic-os commit that vendored the seed.
