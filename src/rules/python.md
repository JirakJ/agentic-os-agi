---
applyTo: "**/*.py"
description: "Python conventions"
---
- Python >= 3.11, managed with `uv` (`uv sync`, `uv run ...`); never call pip directly.
- Full type hints on public signatures; `ruff check --select E,F` and the test suite must be
  clean before commit. Stdlib-first; every dependency must earn its place.
- Real error handling: catch narrowly, fail loudly in libraries, fail safe in hooks.
