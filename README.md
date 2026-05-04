# BloxCue

BloxCue is a standalone local context retrieval layer for AI coding tools. It indexes small markdown knowledge blocks and learned memory, then exposes search and context injection through MCP.

BloxCue v3 is MCP-first for Claude, Codex, Gemini, Cursor, Windsurf, and generic MCP clients. Claude Code hooks are an optional adapter. Continuous-Claude and PostgreSQL are legacy import sources, not required runtime services.

## What Changed In v3

- New default knowledge path: `~/.bloxcue/knowledge`
- Existing `~/.claude-memory` directories remain readable for compatibility
- Learned memory is stored in BloxCue-owned SQLite at `~/.bloxcue/learnings.db`
- Learned memory records use virtual paths like `memory://learning/1`
- Legacy PostgreSQL records can be imported once from Continuous-Claude `archival_memory`
- Claude Code prompt hooks use `hooks/memory-retrieve.py`; the shell hook is only a compatibility shim
- Installer defaults to client-agnostic setup instructions and does not mutate client config unless explicitly requested

## Quick Start

```bash
git clone https://github.com/bokiko/bloxcue.git ~/bloxcue
cd ~/bloxcue
./install.sh --auto
python3 ~/.bloxcue/knowledge/scripts/indexer.py --search "getting started"
```

The installer creates knowledge folders and copies the indexer. It prints MCP setup instructions. It does not install or enable Claude Code hooks unless `--claude-hook` is passed.

## MCP Setup

Use the repository copy of the MCP server:

```json
{
  "mcpServers": {
    "bloxcue": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/USER/bloxcue/scripts/mcp_server.py"],
      "env": {
        "BLOXCUE_MEMORY_DIR": "/home/USER/.bloxcue/knowledge"
      }
    }
  }
}
```

Known config locations:

- Claude Code: `~/.claude/mcp_config.json`
- Cursor: `.cursor/mcp.json`
- Windsurf: `~/.codeium/windsurf/mcp_config.json`
- Generic MCP: use stdio command `python3 /absolute/path/to/scripts/mcp_server.py`

Prefer config snippets for Codex and Gemini unless your installed CLI documents a stable MCP add command.

## Knowledge Blocks

Blocks are markdown files with optional frontmatter:

```markdown
---
title: Production Deploy
category: deployment
tags: [deploy, production]
---

# Production Deploy

Run tests, apply migrations, restart services, and verify health checks.
```

Place blocks under `~/.bloxcue/knowledge`, then index or search:

```bash
python3 ~/.bloxcue/knowledge/scripts/indexer.py
python3 ~/.bloxcue/knowledge/scripts/indexer.py --search "production deploy"
python3 ~/.bloxcue/knowledge/scripts/indexer.py --list
```

If `~/.claude-memory` exists, BloxCue also indexes it as read-compatible legacy knowledge. Legacy entries are exposed with `legacy://claude-memory/...` paths.

## Learned Memory

BloxCue v3 stores learned memory locally in SQLite:

```bash
python3 ~/.bloxcue/knowledge/scripts/indexer.py --add-learning "Use uv for Python project dependency sync" --learning-title "Python dependencies" --learning-tags python,uv
python3 ~/.bloxcue/knowledge/scripts/indexer.py --list-learnings
python3 ~/.bloxcue/knowledge/scripts/indexer.py --search "python dependencies"
```

Learned memory appears in the same index as markdown blocks using `memory://learning/{id}` paths.

## Legacy PostgreSQL Import

PostgreSQL is no longer a default runtime integration. Continuous-Claude users can import existing `archival_memory` rows once:

```bash
BLOXCUE_DATABASE_URL="postgresql://user:pass@host:5432/db" \
  python3 ~/.bloxcue/knowledge/scripts/indexer.py --import-postgres
```

Readable compatibility for old `pg://learning/{uuid}` records remains in the code path, but new learned records should live in SQLite.

## Optional Claude Code Hook

Install the Python hook adapter only when you want automatic `UserPromptSubmit` injection:

```bash
./install.sh --auto --claude-hook
```

Add the printed hook command to `~/.claude/settings.json`. The hook parses stdin JSON, sanitizes `user_prompt`, calls the indexer with `subprocess.run([...], shell=False)`, and emits JSON with `json.dumps`.

## Commands

```bash
# Rebuild index
python3 ~/.bloxcue/knowledge/scripts/indexer.py --rebuild

# Search
python3 ~/.bloxcue/knowledge/scripts/indexer.py --search "query" --limit 5

# JSON search output
python3 ~/.bloxcue/knowledge/scripts/indexer.py --search "query" --json

# Health report
python3 ~/.bloxcue/knowledge/scripts/indexer.py --health

# Add/list learned memory
python3 ~/.bloxcue/knowledge/scripts/indexer.py --add-learning "text" --learning-title "title"
python3 ~/.bloxcue/knowledge/scripts/indexer.py --list-learnings
```

## Environment

| Variable | Default | Purpose |
|---|---:|---|
| `BLOXCUE_MEMORY_DIR` | `~/.bloxcue/knowledge` | Primary markdown knowledge directory |
| `BLOXCUE_LEARNINGS_DB` | `~/.bloxcue/learnings.db` | SQLite learned memory database |
| `BLOXCUE_MAX_TOKENS` | `3000` | Token budget for context injection |
| `BLOXCUE_DATABASE_URL` | unset | Legacy PostgreSQL import URL |
| `BLOXCUE_ENABLE_LEGACY_PG_RUNTIME` | `0` | Temporary compatibility switch for old live PG indexing |

`BLOXCUE_PG_ENABLED` from v2 no longer enables runtime PostgreSQL merging. Use `--import-postgres` for migration; temporary live compatibility requires `BLOXCUE_ENABLE_LEGACY_PG_RUNTIME=1`.

## Verification

Current test discovery should be checked with:

```bash
python3 -m pytest -q
python3 -m py_compile scripts/*.py hooks/*.py
```

## Security

BloxCue reads local markdown and SQLite records. File retrieval blocks path traversal outside configured knowledge directories. Legacy PostgreSQL import uses read-only fetches through `pg_provider.py`.

## License

MIT
