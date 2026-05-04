# Changelog

## 3.0.1 — 2026-05-04

Audit-driven fixes. External code review (Codex) caught 5 real defects in v3.0.0 and a stale SECURITY.md. All fixed transparently — see [`security/2026-05-04-v3-audit-remediation.md`](security/2026-05-04-v3-audit-remediation.md) for the full report.

- **Fix (high)**: Reject symlinks resolving outside the memory root during indexing. Previously a symlink at `~/.bloxcue/knowledge/leak.md → /etc/passwd` would write the target's content into index `preview` fields. The retrieval layer was protected; the index itself was the leak vector.
- **Fix (high)**: Relocate index/usage files to `MEMORY_DIR/.bloxcue/` so the MCP server (running from the repo) and the installed CLI (running from the knowledge dir) share one index. Previously they wrote to different `.index.json` files and search results diverged silently. New env overrides: `BLOXCUE_INDEX_FILE`, `BLOXCUE_USAGE_FILE`. Old caches at `scripts/.index.json` are stale and will be regenerated on next index.
- **Fix (medium)**: Write the index atomically via tempfile + `os.replace()` instead of truncate-then-flock. Closes the race where two concurrent writers could both wipe the index. Drops the `fcntl` import — **BloxCue now runs on Windows.**
- **Fix (medium)**: The Python hook tolerates malformed `BLOXCUE_HOOK_*` env vars instead of raising `ValueError` at import. New `_safe_int` helper mirrors the indexer's existing fallback pattern.
- **Docs**: Rewrite `SECURITY.md` for v3 architecture (was still v2 — referenced `~/.claude-memory` as primary, runtime PG, and old kill switch). Add a v3.0.1 audit remediation report. Vulnerability assessment table now includes the v3.0.0 defects this release fixes.

Tracked, not fixed in this release: 3 low-severity findings (shellcheck warnings, CLI `--limit` validation, `--import-postgres` idempotency). Will land in a follow-up.

## 3.0.0 — 2026-05-04

- Reposition BloxCue as a standalone MCP-first local context retrieval layer for Claude, Codex, Gemini, Cursor, Windsurf, and generic MCP clients.
- Change the default knowledge path from `~/.claude-memory` to `~/.bloxcue/knowledge`.
- Keep existing `~/.claude-memory` directories readable as legacy knowledge.
- Add BloxCue-owned SQLite learned memory at `~/.bloxcue/learnings.db` with `memory://learning/{id}` virtual paths.
- Downgrade Continuous-Claude/PostgreSQL from runtime integration to one-time import compatibility from `archival_memory`.
- Breaking: `BLOXCUE_PG_ENABLED=1` no longer enables runtime PostgreSQL merging. Runtime PG is deprecated and temporarily available only with `BLOXCUE_ENABLE_LEGACY_PG_RUNTIME=1`; use `--import-postgres` to migrate records into SQLite.
- Replace the Claude Code shell hook implementation with a Python hook adapter; keep the shell file as a compatibility shim.
- Change installer behavior to be client-agnostic by default. Claude Code auto-injection is opt-in with `--claude-hook`.
- Add installer detection for `claude`, `codex`, and `gemini`; default installer output prints MCP setup snippets without editing client configuration.
