# Changelog

## Unreleased

- Reposition BloxCue as a standalone MCP-first local context retrieval layer for Claude, Codex, Gemini, Cursor, Windsurf, and generic MCP clients.
- Change the default knowledge path from `~/.claude-memory` to `~/.bloxcue/knowledge`.
- Keep existing `~/.claude-memory` directories readable as legacy knowledge.
- Add BloxCue-owned SQLite learned memory at `~/.bloxcue/learnings.db` with `memory://learning/{id}` virtual paths.
- Downgrade Continuous-Claude/PostgreSQL from runtime integration to one-time import compatibility from `archival_memory`.
- Breaking: `BLOXCUE_PG_ENABLED=1` no longer enables runtime PostgreSQL merging. Runtime PG is deprecated and temporarily available only with `BLOXCUE_ENABLE_LEGACY_PG_RUNTIME=1`; use `--import-postgres` to migrate records into SQLite.
- Replace the Claude Code shell hook implementation with a Python hook adapter; keep the shell file as a compatibility shim.
- Change installer behavior to be client-agnostic by default. Claude Code auto-injection is opt-in with `--claude-hook`.
- Add installer detection for `claude`, `codex`, and `gemini`; default installer output prints MCP setup snippets without editing client configuration.
