# Changelog

## 3.0.2 — 2026-05-05

Polish release. Closes 2 of the 3 deferred low-severity audit findings from v3.0.1, plus a real Python 3.8 compat bug missed in that audit, plus docs/repo hygiene. No behavior change to the search or MCP path.

- **Fix**: `scripts/mcp_server.py` had `handle_message(...) -> dict | None` — PEP 604 union syntax that requires Python 3.10+. The repo (README badge, `AGENTS.md` conventions) promises Python 3.8+, so this would have crashed at import on 3.8/3.9. Changed to `Optional[dict]`.
- **Test**: New `test_shipped_python_files_parse_as_python38` walks `scripts/` and `hooks/` and feeds each file to `ast.parse(..., feature_version=(3, 8))`. Catches PEP 604 unions, dict union via `|`, parenthesized context managers, and any other 3.9+ syntax that would break the documented support floor.
- **Fix**: Clear shellcheck warnings in `install.sh` (5× `read -p` → `read -r -p`, SC2162) and `hooks/memory-retrieve.sh` (`CDPATH=` → `CDPATH=''`, SC2153). Repo now passes `shellcheck install.sh hooks/memory-retrieve.sh` with zero output.
- **Docs**: Rename `CLAUDE.md` → `AGENTS.md` (vendor-neutral filename matching the cross-tool convention used by Claude Code, Codex, Cursor, Windsurf). Content unchanged except the header and intro line.
- **Docs**: README now has a Table of Contents and a "More Documentation" footer linking `AI_SETUP.md`, `SECURITY.md`, `CHANGELOG.md`, the audit reports, releases, and issues. Environment table restructured into core/hook/legacy sections; documents `BLOXCUE_INDEX_FILE`, `BLOXCUE_USAGE_FILE`, and the three `BLOXCUE_HOOK_*` tuning vars added in v3.0.1.
- **Docs**: New `templates/README.md` explaining the directory's purpose (the installer doesn't auto-copy these — they're standalone references).
- **Docs**: Add `CONTRIBUTING.md` with quick rules, dev setup, code conventions (stdlib-only, Python 3.8+, cross-platform), test expectations, and in/out-of-scope guidance.
- **Chore**: Delete two orphan asset files (`assets/bloxcue-v2.png`, `assets/bloxcue2.jpg`) that were no longer referenced after the v3 hero swap. Saves ~830 KB on every clone.
- **Chore**: Reorganize `.gitignore` by purpose; drop dead entries pointing at v2 cache locations that haven't existed since the v3.0.1 path move.

Tests: 213 passing on main (was 212 at v3.0.1). Still tracked, not fixed: `--import-postgres` idempotency (only remaining low-severity audit finding).

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
