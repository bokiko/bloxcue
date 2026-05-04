# Contributing to BloxCue

Thanks for your interest. BloxCue is a small, focused tool — contributions are welcome.

## Quick rules

- Run `pytest tests/` before opening a PR. All 200+ tests should pass.
- Conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`, `ci:`.
- One concern per PR. Bug fixes, features, and doc rewrites get separate PRs.
- No new runtime dependencies in core. BloxCue's zero-dep promise (Python stdlib only) is load-bearing — `psycopg2` is the only optional dep, gated behind try/except.
- No new top-level files unless they're standard (CHANGELOG, LICENSE, README, etc).

## Development setup

```bash
git clone https://github.com/bokiko/bloxcue.git ~/bloxcue
cd ~/bloxcue
python3 -m pytest tests/        # 212 tests, ~1 second
```

No virtualenv or extra setup needed for development — only `pytest` is required and you can install it system-wide or in a venv.

## Code conventions

- Python 3.8+ — don't use 3.9+ syntax (walrus in comprehensions, dict union, etc).
- Type hints on public functions, optional on private helpers.
- Stdlib only in core (`scripts/indexer.py`, `scripts/mcp_server.py`, `hooks/memory-retrieve.py`). PG-related code lives in `scripts/pg_provider.py` and imports `psycopg2` inside try/except.
- Cross-platform: no `fcntl`, no os-specific paths in defaults. The atomic-rename pattern in `write_index_safely` is the reference for how to handle concurrent writes portably.

## Tests

- One file per concern under `tests/unit/`. The convention is `test_<thing>.py` matching the area being tested.
- New features need tests. Bug fixes need a regression test.
- pytest collects modules with `def test_*` functions — no unittest classes with `__init__`.
- Tests should not require running PostgreSQL, network access, or installed AI tools.

## Security

If you discover a security issue, please **do not** open a public GitHub issue. Email the maintainer directly. See [`SECURITY.md`](SECURITY.md) for the full policy and the audit history.

## What's in scope

- Search engine improvements (BM25 tuning, fuzzy matching, intent detection)
- New MCP tools or improvements to existing ones
- Adapter for additional clients (current support: Claude Code, Codex, Gemini, Cursor, Windsurf)
- Performance: indexing speed, search latency
- Cross-platform fixes (Windows in particular)
- Documentation, examples, templates

## What's out of scope

- Cloud sync, network calls, or telemetry. BloxCue is local-only by design.
- LLM API calls. BloxCue is an MCP server; LLMs are the clients.
- Replacing the BM25 engine wholesale. Migration to SQLite FTS5 has been discussed but is a v4-class change requiring a written design doc first.

## Asking questions

- Open a [GitHub Issue](https://github.com/bokiko/bloxcue/issues) — bugs, feature requests, design questions all welcome there.
- Check [Releases](https://github.com/bokiko/bloxcue/releases) for the latest version and migration notes before reporting.
