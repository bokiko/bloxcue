# CLAUDE.md — BloxCue project guide

Internal guide for Claude Code (and other AI assistants) working on this repo. Keep concise. For user-facing docs, see [`README.md`](README.md), [`AI_SETUP.md`](AI_SETUP.md), [`SECURITY.md`](SECURITY.md), [`CONTRIBUTING.md`](CONTRIBUTING.md).

## What this project is

BloxCue is a standalone, MCP-first local context retrieval layer for AI coding tools (Claude Code, Codex, Gemini CLI, Cursor, Windsurf). It indexes markdown blocks under `~/.bloxcue/knowledge/` and learned memory in `~/.bloxcue/learnings.db`, then exposes search and context injection through an MCP stdio server.

**Current release: v3.0.1.** See [`CHANGELOG.md`](CHANGELOG.md) for history.

## Architecture in one paragraph

`scripts/indexer.py` is the engine — pure-Python BM25 + IDF + Porter stemmer + MMR diversity over markdown blocks, merged with SQLite-backed learnings (`memory://learning/{id}`) and legacy `~/.claude-memory/` blocks (`legacy://claude-memory/...`). `scripts/mcp_server.py` is a thin JSON-RPC 2.0 over stdio adapter exposing 6 tools (`search_blocks`, `get_block`, `list_blocks`, `index_blocks`, `block_health`, `inject_context`). `scripts/pg_provider.py` handles the **one-time** import of v2 `archival_memory` rows via `--import-postgres` (no longer a runtime integration). `hooks/memory-retrieve.py` is an optional `UserPromptSubmit` adapter for Claude Code; the `.sh` next to it is a 5-line compatibility shim. `install.sh` is client-agnostic by default — detects `claude`/`codex`/`gemini`, prints MCP setup snippets, never mutates client configs unless `--claude-hook` is passed.

## Conventions (load-bearing)

- **Python 3.8+**, **stdlib only** in core. `psycopg2` is the only optional dep, gated behind `try/except ImportError`. New runtime dependencies need explicit user approval.
- **Cross-platform.** No `fcntl`. Index writes use the atomic-rename pattern (`tempfile + os.replace`) — see `write_index_safely` in `scripts/indexer.py`. The `fcntl` import was removed in v3.0.1.
- **Symlink rejection at index time.** `index_file()` resolves the path before reading and rejects anything outside an allowed knowledge root. Don't add a code path that calls `read_text()` on untrusted user paths without going through `_resolve_entry_path` / the in-root check.
- **Path layout.** The repo lives at `~/bloxcue/`; the user's data lives at `~/.bloxcue/knowledge/`. The installer copies `indexer.py` into the data dir so it can store its index there. `mcp_server.py` stays in the repo.
- **Index/usage state** under `MEMORY_DIR/.bloxcue/` (since v3.0.1). Override via `BLOXCUE_INDEX_FILE` / `BLOXCUE_USAGE_FILE` if needed.
- **Env var naming:** `BLOXCUE_*`. Numeric vars use safe-int parsing with fallbacks (see `_safe_int` in `hooks/memory-retrieve.py` and the `try/except (ValueError, TypeError)` blocks in `scripts/indexer.py`).
- **Conventional commits:** `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`, `ci:`. Messages explain the *why*, not the *what*.
- **No force-push, no `--no-verify`, no direct push to `main`.** All changes via PR. Stacked PRs are fine but never `--delete-branch` on a base that has a dependent open PR — GitHub auto-closes the dependent.

## Workflow for changes

1. `git checkout main && git pull --ff-only origin main`
2. `git checkout -b <type>/<short-name>` (e.g. `fix/symlink-leak`, `docs/readme-toc`)
3. Make the change. **Run `python3 -m pytest tests/ -q` before committing.** All tests must pass.
4. Commit with conventional prefix. Body explains why; one concern per commit.
5. `git push -u origin <branch>` and open a PR with `gh pr create --base main`.
6. Wait for CI (pytest + mirror-to-gitlab). Both must pass.
7. Merge with `gh pr merge <N> --merge --delete-branch`.
8. For releases: cut a CHANGELOG section in a follow-up PR, then push an annotated tag (`git tag -a v3.x.y -m "..."`) and `gh release create`.

## Tests (the contract)

`tests/unit/` has 13 test files, 212 collected. **Don't merge a PR that drops the count or fails any test.** Test conventions:

- pytest-style: `def test_*` functions, no unittest classes with `__init__`.
- One file per concern: `test_bm25_search.py`, `test_pg_integration.py`, `test_audit_v3_0_1.py`, etc.
- Tests must not require running PostgreSQL, network access, or installed AI tools.
- For new features: write the test first. For bugs: write a regression test alongside the fix.

## What's deferred (don't waste effort scoping these without checking with the user)

- **`pyproject.toml` packaging** — would enable `pip install bloxcue` and a `bloxcue` console-script entry point. Big UX win.
- **Indexer module split** — `scripts/indexer.py` is ~1,800 lines doing search + stemmer + scoring + health + CLI + PG import. A clean split into `stemmer.py`, `scoring.py`, `health.py`, `cli.py` is on the backlog but non-trivial without breaking the 212 tests.
- **CI matrix** — currently single Python 3.11 on Ubuntu. Add Windows + macOS + 3.10/3.12/3.13. The Windows path will exercise the atomic-rename fix that replaced `fcntl` in v3.0.1.
- **Migration to SQLite FTS5** — interesting suggestion from external audit, but it's a re-architecture (current implementation has tuned IDF + intent detection + MMR layered on top of BM25). v4-class change requiring a written design doc first.
- **Three low-severity audit findings** still open from the May 2026 audit:
  - shellcheck warnings in `install.sh` and `hooks/memory-retrieve.sh`
  - CLI `--limit` doesn't validate negative/huge values (MCP already does)
  - `--import-postgres` not idempotent (re-running creates duplicate SQLite rows)

## Security model summary

Local-only, no network, no telemetry. Symlinks rejected at index time. Path traversal blocked at retrieval. Index writes are atomic. PG connections (one-time import only) are read-only with parameterized queries. See [`SECURITY.md`](SECURITY.md) for the full policy and audit history; see `security/2026-02-06-audit-remediation.md` (v2 audit) and `security/2026-05-04-v3-audit-remediation.md` (v3.0.1 audit) for the per-finding detail.

## Where things are

| Path | What |
|---|---|
| `scripts/indexer.py` | BM25 engine, SQLite learnings, CLI |
| `scripts/mcp_server.py` | JSON-RPC 2.0 over stdio MCP server |
| `scripts/pg_provider.py` | Optional PG importer (one-time only) |
| `hooks/memory-retrieve.py` | Optional Claude Code `UserPromptSubmit` hook |
| `hooks/memory-retrieve.sh` | 5-line shim for v2 hook installs |
| `install.sh` | Client-agnostic installer with `--auto`, `--claude-hook` flags |
| `tests/unit/` | 212 pytest tests, organized by concern |
| `templates/` | Sample knowledge blocks (not auto-installed) |
| `assets/` | Repo images (currently just `bloxcue-v3.jpg`) |
| `security/` | Audit reports, one per audit |
| `.github/workflows/` | `test.yml` (pytest) + `mirror-gitlab.yml` |

## Things to verify before claiming a fix works

- `python3 -m pytest tests/ -q` passes (currently 212).
- `python3 -m py_compile scripts/*.py hooks/*.py` exits 0.
- `bash -n install.sh hooks/memory-retrieve.sh` exits 0.
- For installer changes: smoke-test on a real machine. Tests don't catch installer-script regressions.
- For doc changes: every file path in changed text actually resolves.
