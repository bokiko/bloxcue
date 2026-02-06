# BloxCue AI Setup Guide

> **This file is for AI assistants.** Humans: see [README.md](README.md) for the full guide.

This is a structured, machine-parseable setup guide. Every instruction is a runnable command. Defaults are explicit. No interactive input is needed.

---

## Prerequisites

| Requirement | Check command | Install if missing |
|---|---|---|
| Python 3.8+ | `python3 --version` | `apt install python3` / `brew install python3` |
| Git | `git --version` | `apt install git` / `brew install git` |

---

## Quick Reference

| Fact | Value |
|---|---|
| Repo URL | `https://github.com/bokiko/bloxcue.git` |
| Default clone path | `~/bloxcue` |
| Global memory dir | `~/.claude-memory` |
| Project memory dir | `./claude-memory` (relative to project root) |
| Dependencies | **Zero** (pure Python stdlib) |
| PostgreSQL | Optional add-on, not required |
| MCP server script | `<bloxcue-dir>/scripts/mcp_server.py` |
| Indexer script | `<memory-dir>/scripts/indexer.py` |
| Hook script | `~/.claude/hooks/memory-retrieve.sh` |

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/bokiko/bloxcue.git ~/bloxcue
cd ~/bloxcue
```

If already cloned, skip to Step 2.

---

## Step 2 — Choose Installation Scope

| Option | Flag value | What it does |
|---|---|---|
| Global only | `--scope 1` | Creates `~/.claude-memory` |
| Project only | `--scope 2` | Creates `./claude-memory` in current directory |
| Both (default) | `--scope 3` | Creates both global and project directories |

**Default: 3 (both).** Use scope 1 if the user only wants global, scope 2 for project-only.

---

## Step 3 — Choose Directory Structure

| Option | Flag value | Folders created |
|---|---|---|
| By Subject (default) | `--structure 1` | `guides/` `references/` `projects/` `configs/` `notes/` |
| By Project | `--structure 2` | `project-a/` `project-b/` `shared/` |
| Developer | `--structure 3` | `apis/` `databases/` `deployment/` `frontend/` `backend/` `notes/` |
| DevOps | `--structure 4` | `servers/` `networking/` `monitoring/` `security/` `runbooks/` |
| Minimal | `--structure 5` | `docs/` `notes/` |
| Custom | `--structure 6` | `docs/` `notes/` (default in auto mode) |

**Default: 1 (by subject).**

---

## Step 4 — Run the Installer

### Option A: Non-interactive (recommended for AI)

```bash
cd ~/bloxcue && ./install.sh --auto
```

This uses defaults: scope=3 (both), structure=1 (by subject).

To override defaults:

```bash
cd ~/bloxcue && ./install.sh --auto --scope 1 --structure 3
```

Environment variables also work (lower priority than flags):

```bash
BLOXCUE_SCOPE=1 BLOXCUE_STRUCTURE=3 ./install.sh --auto
```

### Option B: Manual steps (if install.sh fails)

```bash
# Create directories (scope=3, structure=1 example)
mkdir -p ~/.claude-memory/{guides,references,projects,configs,notes,scripts}
mkdir -p ./claude-memory/{guides,references,projects,configs,notes,scripts}

# Copy indexer
cp ~/bloxcue/scripts/indexer.py ~/.claude-memory/scripts/
cp ~/bloxcue/scripts/indexer.py ./claude-memory/scripts/

# Copy hook
mkdir -p ~/.claude/hooks
cp ~/bloxcue/hooks/memory-retrieve.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/memory-retrieve.sh

# Update hook path (set MEMORY_PATH to the primary install location)
sed -i 's|MEMORY_PATH=.*|MEMORY_PATH="$HOME/.claude-memory"|' ~/.claude/hooks/memory-retrieve.sh
```

### What install.sh --auto does

1. Creates memory directories with chosen folder structure
2. Copies `indexer.py` into each memory directory's `scripts/`
3. Creates a `getting-started.md` example block
4. Installs the auto-retrieval hook to `~/.claude/hooks/`
5. Updates `~/.claude/settings.json` (creates or prints instructions)
6. Runs initial index

---

## Step 5 — Configure MCP Server

Add the BloxCue MCP server to the appropriate config file for your client. Replace `/home/USER/bloxcue` with the actual clone path.

### Claude Code

File: `~/.claude/mcp_config.json`

```json
{
  "mcpServers": {
    "bloxcue": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/USER/bloxcue/scripts/mcp_server.py"]
    }
  }
}
```

### Cursor

File: `.cursor/mcp.json` (in project root)

```json
{
  "mcpServers": {
    "bloxcue": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/USER/bloxcue/scripts/mcp_server.py"]
    }
  }
}
```

### Windsurf

File: `~/.codeium/windsurf/mcp_config.json`

```json
{
  "mcpServers": {
    "bloxcue": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/USER/bloxcue/scripts/mcp_server.py"]
    }
  }
}
```

### Generic MCP client

Any MCP client that supports stdio transport:

```json
{
  "type": "stdio",
  "command": "python3",
  "args": ["<absolute-path-to>/bloxcue/scripts/mcp_server.py"]
}
```

### With PostgreSQL (optional)

Add an `env` block to any of the above configs:

```json
{
  "mcpServers": {
    "bloxcue": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/USER/bloxcue/scripts/mcp_server.py"],
      "env": {
        "BLOXCUE_DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname",
        "BLOXCUE_MEMORY_DIR": "/home/USER/.claude-memory"
      }
    }
  }
}
```

---

## Step 6 — Configure Auto-Retrieval Hook (Claude Code only)

The installer handles this automatically. If manual setup is needed, add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "~/.claude/hooks/memory-retrieve.sh"
      }]
    }]
  }
}
```

If `settings.json` already exists, merge the `UserPromptSubmit` entry into the existing `hooks` object.

Restart Claude Code after changing settings.

---

## Step 7 — Verify Installation

Run these commands and check the expected output:

```bash
# Check indexer works (should print index stats or "No blocks found")
python3 ~/.claude-memory/scripts/indexer.py

# Search for the getting-started block (should return 1 result)
python3 ~/.claude-memory/scripts/indexer.py --search "getting started"

# List all blocks (should show at least getting-started.md)
python3 ~/.claude-memory/scripts/indexer.py --list
```

If using MCP, verify the server starts without errors:

```bash
python3 ~/bloxcue/scripts/mcp_server.py 2>&1 | head -5
```

---

## Step 8 — Create the First Block

Blocks are markdown files with YAML frontmatter. Place them in any subfolder of the memory directory.

### Format

```markdown
---
title: Short Descriptive Title
category: folder-name
tags: [keyword1, keyword2, keyword3]
---

# Content here

Your documentation, guides, references, code snippets, etc.
```

### Example

```bash
cat > ~/.claude-memory/guides/my-api.md << 'EOF'
---
title: My API Reference
category: guides
tags: [api, rest, authentication]
---

# My API Reference

Base URL: https://api.example.com

## Authentication
Bearer token in Authorization header.

## Endpoints
- GET /users - List users
- POST /users - Create user
EOF
```

### Re-index after adding blocks

```bash
python3 ~/.claude-memory/scripts/indexer.py
```

---

## Updating BloxCue

```bash
cd ~/bloxcue && git pull
```

That's it. Existing blocks and configuration are not affected.

---

## Optional: PostgreSQL Integration

For [Continuous-Claude](https://github.com/parcadei/Continuous-Claude-v3) users who want unified search across markdown blocks and session learnings.

### Requirements

- PostgreSQL with `archival_memory` table
- `psycopg2-binary`: `pip install psycopg2-binary`

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `BLOXCUE_DATABASE_URL` | Yes | PostgreSQL connection URL |
| `BLOXCUE_PG_ENABLED` | No | Set `0` to disable (default: `1`) |
| `BLOXCUE_PG_CACHE_TTL` | No | Cache seconds (default: `300`) |
| `DATABASE_URL` | No | Fallback if `BLOXCUE_DATABASE_URL` not set |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `command not found: python3` | Python not installed | `apt install python3` or `brew install python3` |
| `No results found` when searching | Index not built | Run `python3 ~/.claude-memory/scripts/indexer.py` |
| `No results found` after indexing | Files missing `.md` extension or no frontmatter | Ensure files end in `.md` and have `---` frontmatter |
| Hook not triggering | `settings.json` not configured or Claude Code not restarted | Check `~/.claude/settings.json` has the hook entry; restart Claude Code |
| MCP server not connecting | Path in config is wrong or not absolute | Use absolute path to `mcp_server.py` in config |
| MCP server import error | Running Python < 3.8 | Upgrade Python: `python3 --version` should be 3.8+ |
| PostgreSQL results missing | `psycopg2` not installed or URL wrong | `pip install psycopg2-binary` and verify `BLOXCUE_DATABASE_URL` |

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `BLOXCUE_MEMORY_DIR` | Parent of `scripts/` | Path to blocks directory |
| `BLOXCUE_MAX_TOKENS` | `3000` | Token budget for `inject_context` |
| `BLOXCUE_DATABASE_URL` | *(none)* | PostgreSQL connection URL |
| `BLOXCUE_PG_ENABLED` | `1` | Set `0` to disable PostgreSQL |
| `BLOXCUE_PG_CACHE_TTL` | `300` | Seconds before PG cache refresh |
| `DATABASE_URL` | *(none)* | Fallback PostgreSQL URL |
| `BLOXCUE_SCOPE` | *(none)* | Install scope for `--auto` (1/2/3) |
| `BLOXCUE_STRUCTURE` | *(none)* | Install structure for `--auto` (1-6) |

---

## MCP Tools Reference

| Tool | Description |
|---|---|
| `search_blocks` | Search blocks with BM25 scoring, returns ranked results with scores |
| `get_block` | Retrieve full content of a block by path |
| `list_blocks` | List all indexed blocks, optionally filtered by category |
| `index_blocks` | Rebuild the search index |
| `block_health` | Health report: freshness, coverage gaps, suggestions |
| `inject_context` | One-shot: search + rank + deduplicate + token-budget + format |
