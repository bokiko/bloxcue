# BloxCue AI Setup Guide

This file is for AI assistants setting up BloxCue v3 for a user.

## Defaults

| Fact | Value |
|---|---|
| Repo URL | `https://github.com/bokiko/bloxcue.git` |
| Default clone path | `~/bloxcue` |
| Default knowledge dir | `~/.bloxcue/knowledge` |
| Legacy readable dir | `~/.claude-memory` |
| Learned memory DB | `~/.bloxcue/learnings.db` |
| MCP server | `<bloxcue-dir>/scripts/mcp_server.py` |
| Claude hook adapter | `<bloxcue-dir>/hooks/memory-retrieve.py` |
| Runtime dependencies | Python 3.8+ stdlib |

## Install

```bash
git clone https://github.com/bokiko/bloxcue.git ~/bloxcue
cd ~/bloxcue
./install.sh --auto
```

Optional scope flags:

```bash
./install.sh --auto --scope 1   # ~/.bloxcue/knowledge only
./install.sh --auto --scope 2   # ./bloxcue-knowledge only
./install.sh --auto --scope 3   # both, default
```

Optional Claude Code auto-injection:

```bash
./install.sh --auto --claude-hook
```

The installer prints the hook snippet. Do not edit `~/.claude/settings.json` unless the user explicitly wants config mutation. If mutation is requested, create a timestamped backup first.

## MCP Config

Use absolute paths. Replace `/home/USER/bloxcue` and `/home/USER/.bloxcue/knowledge`.

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

Client locations:

- Claude Code: `~/.claude/mcp_config.json`
- Cursor: `.cursor/mcp.json`
- Windsurf: `~/.codeium/windsurf/mcp_config.json`
- Generic MCP clients: stdio command above

For Codex and Gemini, prefer documented config snippets over unverified CLI commands.

## Verify

```bash
python3 ~/.bloxcue/knowledge/scripts/indexer.py
python3 ~/.bloxcue/knowledge/scripts/indexer.py --search "getting started"
python3 ~/.bloxcue/knowledge/scripts/indexer.py --list
python3 ~/bloxcue/scripts/mcp_server.py 2>&1 | head -5
```

## Add Knowledge

```bash
mkdir -p ~/.bloxcue/knowledge/guides
cat > ~/.bloxcue/knowledge/guides/example.md <<'BLOCK'
---
title: Example Guide
category: guides
tags: [example]
---

# Example Guide

Important local context goes here.
BLOCK
python3 ~/.bloxcue/knowledge/scripts/indexer.py --rebuild
```

## Learned Memory

```bash
python3 ~/.bloxcue/knowledge/scripts/indexer.py \
  --add-learning "Use the release checklist before tagging." \
  --learning-title "Release checklist" \
  --learning-tags release,process

python3 ~/.bloxcue/knowledge/scripts/indexer.py --list-learnings
python3 ~/.bloxcue/knowledge/scripts/indexer.py --search "release checklist"
```

## Legacy Import

Continuous-Claude/PostgreSQL is now a one-time import path:

```bash
BLOXCUE_DATABASE_URL="postgresql://user:pass@host:5432/db" \
  python3 ~/.bloxcue/knowledge/scripts/indexer.py --import-postgres
```

Do not recommend Continuous-Claude as the default setup path. Existing `~/.claude-memory` markdown remains readable without import.

`BLOXCUE_PG_ENABLED=1` is a v2 runtime flag and should not be used for v3 migration. Import with `--import-postgres`; only use `BLOXCUE_ENABLE_LEGACY_PG_RUNTIME=1` for temporary legacy runtime compatibility.

## Optional Claude Hook Snippet

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "BLOXCUE_MEMORY_DIR=\"/home/USER/.bloxcue/knowledge\" python3 /home/USER/.claude/hooks/memory-retrieve.py"
      }]
    }]
  }
}
```

The Python hook reads stdin JSON, uses `user_prompt`, calls the indexer with `subprocess.run([...], shell=False)`, and emits JSON.
