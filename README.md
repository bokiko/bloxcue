<div align="center">

# BloxCue

<h3>The search engine for your AI context. Files, databases, one interface.</h3>

<p>
  <img src="https://img.shields.io/badge/v2.0-MCP%20Server%20%2B%20PostgreSQL-blueviolet?style=for-the-badge" alt="v2.0" />
  <a href="https://github.com/parcadei/Continuous-Claude-v3">
    <img src="https://img.shields.io/badge/Integrates-Continuous--Claude-blue?style=for-the-badge" alt="Integrates Continuous-Claude" />
  </a>
</p>

<p>
  <a href="#quick-start">
    <img src="https://img.shields.io/badge/setup-5%20minutes-success" alt="5 min setup" />
  </a>
  <a href="#token-savings">
    <img src="https://img.shields.io/badge/saves-7000+%20tokens%2Fprompt-orange" alt="7000+ tokens saved" />
  </a>
  <a href="#mcp-server">
    <img src="https://img.shields.io/badge/MCP-6%20tools-informational" alt="6 MCP tools" />
  </a>
  <a href="#postgresql-integration">
    <img src="https://img.shields.io/badge/PostgreSQL-optional-9cf" alt="PG integration" />
  </a>
  <a href="https://github.com/bokiko/bloxcue/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License" />
  </a>
</p>

<p>
  <a href="https://bokiko.io">bokiko.io</a> · <a href="https://twitter.com/bokiko">@bokiko</a> · <a href="https://medium.com/@bokiko/my-claude-md-got-too-big-so-i-built-bloxcue-91eca1e53059">Read the story on Medium</a>
</p>

</div>

---

<p align="center">
  <img src="bloxcue2.jpg" alt="BloxCue - Context blocks for Claude Code" width="600" />
</p>

---

## Table of Contents

1. [The Story](#the-story)
2. [Quick Start](#quick-start)
3. [Upgrading from v1?](#upgrading-from-v1)
4. [Architecture](#architecture)
5. [Features](#features)
6. [MCP Server](#mcp-server)
7. [PostgreSQL Integration](#postgresql-integration)
8. [Who is this for?](#who-is-this-for)
9. [How it works](#how-it-works)
10. [Requirements](#requirements)
11. [Enable Auto-Retrieval](#enable-auto-retrieval)
12. [After Installation](#after-installation)
13. [For Existing Claude Users](#for-existing-claude-users)
14. [Token Savings](#token-savings)
15. [Directory Structure](#directory-structure)
16. [Commands Reference](#commands-reference)
17. [Configuration](#configuration)
18. [Best Practices](#best-practices)
19. [FAQ](#faq)
20. [Troubleshooting](#troubleshooting)
21. [Security](#security)
22. [Roadmap](#roadmap)
23. [Contributing](#contributing)
24. [Credits](#credits)

---

## The Story

After using [Continuous-Claude](https://github.com/parcadei/Continuous-Claude-v3) (created by [parcadei](https://github.com/parcadei)), we noticed something: our `CLAUDE.md` files kept growing. Every time we documented something new, added a guide, or saved a configuration, the file got bigger.

**The problem?** Claude loads your entire `CLAUDE.md` on every single prompt. That 30KB file? Loaded 20+ times per session. Hundreds of thousands of tokens wasted on content Claude didn't need.

**Why does this matter?** Whether you're on Claude Pro ($20/month) or Pro Max ($200/month), you have a monthly token budget. Wasting thousands of tokens per prompt on irrelevant context means fewer tokens for actual thinking, coding, and building.

**The solution:** What if Claude could pull in just the context it needs? You ask about your database, Claude grabs the database block. You ask about deployment, Claude grabs the deployment block. Everything else stays on the shelf.

That's **BloxCue** - intelligent context blocks that get loaded when you need them.

**v2** takes it further: an MCP server with 6 tools, token-budgeted context injection, and optional PostgreSQL integration that unifies your curated markdown blocks with learned memory from [Continuous-Claude](https://github.com/parcadei/Continuous-Claude-v3).

---

## Quick Start

Choose your integration:

| Mode | Best For | Setup |
|------|----------|-------|
| **MCP Server** (v2.0) | Any MCP client (Claude, Cursor, Windsurf) | Add to `mcp_config.json` |
| **Auto-Injection Hooks** | Claude Code with automatic context | Run `install.sh` |

> **AI assistants:** See [AI_SETUP.md](AI_SETUP.md) for structured setup instructions.

> **No database? No problem.** BloxCue works 100% with markdown files only. PostgreSQL is an optional add-on for [Continuous-Claude](https://github.com/parcadei/Continuous-Claude-v3) users.

### Option 1: Let Your AI Install It (Recommended)

Paste this into any AI assistant (Claude Code, Cursor, Windsurf, etc.):

```
Set up BloxCue from https://github.com/bokiko/bloxcue

1. Clone to ~/bloxcue (or wherever I prefer)
2. Read AI_SETUP.md for setup instructions
3. Run ./install.sh --auto (or ask me about scope/structure preferences)
4. Configure MCP server per AI_SETUP.md Step 5
5. Verify: python3 ~/.claude-memory/scripts/indexer.py --search "test"
6. Help me create my first block from something in my CLAUDE.md
```

Your AI reads [AI_SETUP.md](AI_SETUP.md) and handles everything — no manual steps needed.

---

### Option 2: Manual Installation

#### Step 1: Install Continuous-Claude

Follow our [Continuous-Claude v3](https://github.com/parcadei/Continuous-Claude-v3).

#### Step 2: Clone BloxCue

```bash
git clone https://github.com/bokiko/bloxcue.git
cd bloxcue
```

#### Step 3: Run the installer

```bash
./install.sh
```

The installer will ask you:

**Where to install?**
- **Global** (`~/.claude-memory`) - knowledge used across all projects
- **Project** (`./claude-memory`) - project-specific docs only
- **Both** - recommended for most users

**How to organize?**
- **By subject** - guides, references, projects (general use)
- **By project** - project-a, project-b (freelancers/agencies)
- **Developer** - apis, databases, deployment, frontend, backend
- **DevOps** - servers, networking, monitoring, security
- **Minimal** - just docs and notes
- **Custom** - you specify

#### Step 4: Add your first block

```bash
nano ~/.claude-memory/guides/deployment.md
```

```markdown
---
title: Production Deployment
category: guides
tags: [deployment, production, devops]
---

# Production Deployment

## Prerequisites
- SSH access to production server
- Environment variables configured

## Deploy Steps
1. Run tests locally
2. Push to main branch
3. SSH into server
4. Pull latest changes
5. Run migrations
6. Restart services

## Rollback
1. Revert to previous commit
2. Run down migrations
3. Restart services
```

#### Step 5: Index your blocks

```bash
python3 ~/.claude-memory/scripts/indexer.py
```

#### Step 6: Test it

```bash
python3 ~/.claude-memory/scripts/indexer.py --search "deployment"
```

---

## Upgrading from v1?

```bash
cd ~/bloxcue && git pull
# Done. Seriously.
```

MCP server and PostgreSQL are opt-in additions. Your existing blocks, hooks, and workflows continue unchanged. Turn on new features when you're ready.

Or paste this to Claude:

```
Update BloxCue to v2 by running git pull in my bloxcue directory.
Show me what's new and help me enable MCP server if I haven't already.
```

---

## Architecture

```
                    +---------------------------+
                    |     Claude Code / MCP      |
                    |        Client              |
                    +------------+--------------+
                                 |
                          JSON-RPC (stdio)
                                 |
                    +------------+--------------+
                    |    BloxCue MCP Server      |
                    |    (mcp_server.py)          |
                    |                            |
                    |  6 tools:                  |
                    |  - search_blocks           |
                    |  - get_block               |
                    |  - list_blocks             |
                    |  - index_blocks            |
                    |  - block_health            |
                    |  - inject_context          |
                    +------+----------+----------+
                           |          |
              +------------+    +-----+-----------+
              |                 |                  |
    +---------v--------+  +----v--------------+   |
    |  Markdown Files  |  |  PostgreSQL       |   |
    |  (.md blocks)    |  |  (optional)       |   |
    |                  |  |                   |   |
    |  guides/         |  |  archival_memory  |   |
    |  references/     |  |  table            |   |
    |  configs/        |  |  (pgvector)       |   |
    +------------------+  +-------------------+   |
              |                 |                  |
              +--------+--------+                  |
                       |                           |
              +--------v-----------+               |
              |   Unified Index    |               |
              |                    |               |
              |  BM25 + IDF +      |               |
              |  Porter Stemmer +  |               |
              |  Intent Detection  +<--------------+
              |  + MMR Diversity   |    UserPromptSubmit
              |                    |    hook (auto-inject)
              +--------------------+
```

**Two retrieval paths, one search interface.** Markdown files and PostgreSQL learnings are merged into a single BM25 index. The MCP server and CLI hook both query the same engine.

---

## Features

### Search Engine

| Feature | Description |
|---------|-------------|
| **BM25 Scoring** | Industry-standard probabilistic ranking (same algorithm as Elasticsearch) |
| **Porter Stemmer** | Matches word variations (`running` -> `run`, `deployment` -> `deploy`) |
| **IDF Weighting** | Rare terms rank higher than common ones for better precision |
| **Bigram Matching** | Recognizes multi-word phrases like "error handling" |
| **Query Intent Detection** | Adjusts scoring based on query type (how-to, troubleshooting, concept, reference) |
| **Synonym Expansion** | 50+ tech term mappings (`k8s` -> `kubernetes`, `auth` -> `authentication`) |
| **MMR Diversity** | Prevents redundant results using Maximal Marginal Relevance |
| **Memoized Stemming** | LRU cache on stemmer for 50-70% faster repeated searches |
| **Index Caching** | In-memory cache with mtime checking eliminates repeated disk reads |

### Token-Budgeted Context Injection

BloxCue doesn't just find relevant blocks - it manages your token budget:

```
Token budget: 3000

Block 1 (score: 12.4, 800 tokens) -> Full content injected
Block 2 (score: 8.1, 2500 tokens) -> Summary injected (over budget for full)
Block 3 (score: 5.2, 1200 tokens) -> Reference only (path + title)
```

- **Full content** for top-ranked blocks that fit
- **Summaries** (first 300 chars) for blocks that partially fit
- **References** (title + path) for the rest
- Configurable budget via `BLOXCUE_MAX_TOKENS` or per-call

### Automatic Context Injection

- Hooks into Claude Code's `UserPromptSubmit` event
- Analyzes your prompt in real-time
- Injects only the most relevant blocks as context
- Zero manual intervention required

### Zero Dependencies (Core)

- Pure Python standard library - no pip installs required
- PostgreSQL integration is **optional** (`psycopg2` imported in try/except)
- Works offline, works anywhere Python 3.8+ runs
- No env vars needed for default behavior

---

## MCP Server

BloxCue v2 ships with a full MCP (Model Context Protocol) server, making it compatible with any MCP client: Claude Code, Cursor, Windsurf, and more.

### Tools

| Tool | Description |
|------|-------------|
| `search_blocks` | Search with BM25 scoring, returns ranked results with scores and previews |
| `get_block` | Retrieve full content of a specific block by path |
| `list_blocks` | List all indexed blocks, optionally filtered by category |
| `index_blocks` | Rebuild the search index (run after adding/editing blocks) |
| `block_health` | Health report: freshness, coverage gaps, and improvement suggestions |
| `inject_context` | **One-shot retrieval**: search + rank + deduplicate + token-budget + format |

### Setup

Add to your MCP config (e.g., `~/.claude/mcp_config.json`):

```json
{
  "mcpServers": {
    "bloxcue": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/bloxcue/scripts/mcp_server.py"]
    }
  }
}
```

Once configured, your AI assistant can call BloxCue tools directly. No hooks needed - tools are self-documenting via MCP `tools/list`.

### Example: inject_context

The most powerful tool. One call does search + rank + deduplicate + budget:

```
Tool call: inject_context(query="deployment guide", max_tokens=2000)

Response:
[BloxCue: Injected 3 block(s), ~1847 tokens, query: "deployment guide"]
---

### Block 1: Production Deployment (score: 14.2, updated: 2 days ago)
Tags: deployment, production, aws

# Production Deployment
## Prerequisites
- SSH access to production server
...

### Block 2: CI/CD Pipeline (score: 8.7, updated: 5 days ago)
[Summary - full block at: guides/cicd.md]

Our CI/CD pipeline uses GitHub Actions to...

### Block 3: Server Configuration (score: 5.1, updated: 12 days ago)
[Reference only - retrieve full block with: get_block("configs/servers.md")]
```

---

## PostgreSQL Integration

BloxCue can optionally connect to a PostgreSQL database to search **learned memory** alongside markdown files. This is designed for [Continuous-Claude](https://github.com/parcadei/Continuous-Claude-v3)'s `archival_memory` table but works with any compatible schema.

### What it does

- Fetches session learnings from PostgreSQL at index time
- Converts them to BloxCue index entries with `pg://learning/{uuid}` virtual paths
- Merges them into the BM25 index alongside file entries
- Search results show `[PG]` labels for database-sourced entries
- Full content retrieval works transparently for both files and PG entries

### How it works

```
You: "How did we fix that auth hook error?"

BloxCue searches BOTH:
  1. Markdown files (guides/auth.md, references/hooks.md)
  2. PostgreSQL learnings (past session where you fixed it)

Results:
  1. [PG] Error Fix: hook authentication (score: 11.2)  <-- from database
  2. Authentication Guide (score: 8.4)                   <-- from file
  3. [PG] Working Solution: token refresh (score: 6.1)   <-- from database
```

### Enable PostgreSQL

Add env vars to your MCP config:

```json
{
  "mcpServers": {
    "bloxcue": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/bloxcue/scripts/mcp_server.py"],
      "env": {
        "BLOXCUE_DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname",
        "BLOXCUE_MEMORY_DIR": "/path/to/bloxcue"
      }
    }
  }
}
```

Or set the environment variables directly:

```bash
export BLOXCUE_DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
```

### Safety

- **Optional**: `psycopg2` is imported in a try/except. Without it, BloxCue works identically to before.
- **Kill switch**: Set `BLOXCUE_PG_ENABLED=0` to disable even if a URL is configured.
- **Non-fatal**: Every database call is wrapped in try/except. PG errors are logged to stderr; file search always works.
- **Read-only**: All database connections use `readonly=True`. BloxCue never writes to your database.
- **Cache TTL**: PG learnings are cached and refreshed every 5 minutes (configurable via `BLOXCUE_PG_CACHE_TTL`).

---

## Who is this for?

| If you're... | BloxCue helps you... |
|--------------|----------------------|
| **A Claude Code user** | Stop burning tokens on unused context |
| **Using Continuous-Claude** | Search your curated blocks AND learned memory in one place |
| **Managing multiple configs** | Keep docs, guides, and configs organized and searchable |
| **Building MCP integrations** | 6 tools available via standard MCP protocol |
| **Working on several projects** | Switch context without reloading everything |
| **Hitting token limits** | Save ~7,000 tokens per prompt |
| **New to Claude Code** | Start with good habits from day one |

---

## How it works

**Before BloxCue:**
```
You: "How do I deploy to production?"

Claude loads: ENTIRE CLAUDE.md (34KB = ~8,500 tokens)
  - Your coding standards (not needed)
  - Your API documentation (not needed)
  - Your 10 different project configs (not needed)
  - Your deployment guide (NEEDED!)
  - Everything else (not needed)

Result: ~8,500 tokens loaded, only ~800 were relevant
```

**After BloxCue:**
```
You: "How do I deploy to production?"

BloxCue: Detects "deploy" + "production" keywords
         -> Stems to "deploy" + "product"
         -> Expands with synonyms: "release", "deployment"
         -> BM25 ranks deployment block highest (IDF boost)
         -> Intent: "howto" -> boosts tags & keywords
         -> Token budget: injects full content (within budget)

Claude loads: Just the deployment block (~800 tokens)

Result: ~800 tokens loaded, all relevant
Saved: ~7,700 tokens for thinking & coding
```

---

## Requirements

### Continuous-Claude (Recommended)

BloxCue works best alongside Continuous-Claude. They're complementary tools:

| Tool | Purpose |
|------|---------|
| **Continuous-Claude** | Session memory (ledgers, handoffs, learnings) |
| **BloxCue** | Knowledge retrieval (on-demand context loading) |

**Think of it this way:**
- Continuous-Claude = Claude's **memory** (what to remember)
- BloxCue = Claude's **filing cabinet** (where to find it efficiently)

With PostgreSQL integration enabled, BloxCue becomes the **unified search interface** for both.

If you prefer manual setup, follow our [Continuous-Claude v3](https://github.com/parcadei/Continuous-Claude-v3) first.

> **Credit:** Continuous-Claude was created by [parcadei](https://github.com/parcadei). Check out [Continuous-Claude v3](https://github.com/parcadei/Continuous-Claude-v3).

---

## Enable Auto-Retrieval

**Required for BloxCue to work automatically.**

### Add the hook to settings.json

```bash
nano ~/.claude/settings.json
```

Add to your hooks section:

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

### Restart Claude Code

Close and reopen Claude Code for changes to take effect.

### Test it

```
You: "How do I deploy to production?"
```

Claude will automatically receive your deployment block as context.

---

## After Installation

> **Important:** BloxCue is installed, but you're still wasting tokens until you slim your CLAUDE.md!

**Ask Claude to migrate your content:**

```
My CLAUDE.md has grown too big. Help me migrate content to BloxCue blocks:
1. Read my current CLAUDE.md
2. Identify distinct topics (deployment, APIs, configs, etc.)
3. Create separate block files in ~/.claude-memory/
4. Slim my CLAUDE.md to essentials only
5. Re-index with: python3 ~/.claude-memory/scripts/indexer.py
```

**Your CLAUDE.md should end up like this:**

```markdown
# My Workspace

Knowledge base at `~/.claude-memory/`.
Claude retrieves relevant context automatically via hooks.

## Essentials
- Project: MyApp
- Stack: Node.js, PostgreSQL, Redis
```

---

## For Existing Claude Users

Already have a big `CLAUDE.md` file?

### Let Claude migrate for you (Recommended)

```
I have an existing CLAUDE.md file that's gotten too big.
Help me migrate it to BloxCue by:
1. Reading my current CLAUDE.md
2. Identifying distinct topics
3. Creating separate block files for each topic
4. Updating my CLAUDE.md to be minimal
```

### Starting fresh?

1. Let Claude install Continuous-Claude + BloxCue
2. Start with a minimal CLAUDE.md
3. Add blocks as you go

Your CLAUDE.md stays small forever because everything goes into blocks.

---

## Token Savings

Real numbers from actual usage:

| Metric | Before BloxCue | After BloxCue | Saved |
|--------|----------------|---------------|-------|
| Tokens per prompt | ~8,500 | ~1,000 | **~7,500** |
| Tokens per session (20 prompts) | ~170,000 | ~20,000 | **~150,000** |
| Reduction | - | - | **~88%** |

### What this means

Saved tokens go toward:
- **Deeper reasoning** - Claude can think more thoroughly
- **Longer sessions** - Stay within context limits longer
- **Faster responses** - Less to process means quicker replies

---

## Directory Structure

### By Subject (Default)

```
~/.claude-memory/
├── guides/             # How-to guides
├── references/         # Quick reference docs
├── projects/           # Project-specific info
├── configs/            # Configuration templates
├── notes/              # General notes
├── scripts/
│   ├── indexer.py      # Search engine + index builder
│   ├── mcp_server.py   # MCP server (6 tools)
│   └── pg_provider.py  # PostgreSQL integration (optional)
└── tests/
    └── unit/           # 245+ unit tests
```

### By Project

```
~/.claude-memory/
├── client-alpha/
│   ├── requirements.md
│   ├── api.md
│   └── contacts.md
├── client-beta/
│   └── ...
└── scripts/
```

---

## Commands Reference

### CLI

```bash
# Index all blocks
python3 ~/.claude-memory/scripts/indexer.py

# Search for something
python3 ~/.claude-memory/scripts/indexer.py --search "keyword"

# Search with verbose output (shows scores)
python3 ~/.claude-memory/scripts/indexer.py --search "keyword" -v

# List all indexed blocks
python3 ~/.claude-memory/scripts/indexer.py --list

# Rebuild index from scratch
python3 ~/.claude-memory/scripts/indexer.py --rebuild

# Output as JSON
python3 ~/.claude-memory/scripts/indexer.py --search "keyword" --json
```

### MCP Tools

Once the MCP server is configured, these tools are available to any MCP client:

```
search_blocks(query="auth errors", limit=5)
get_block(path="guides/authentication.md")
list_blocks(category="guides")
index_blocks(force=true)
block_health()
inject_context(query="deployment", max_tokens=2000, limit=5)
```

---

## Configuration

All configuration is via environment variables. **None are required** - defaults match the original behavior.

| Variable | Default | Description |
|----------|---------|-------------|
| `BLOXCUE_MEMORY_DIR` | Parent of scripts/ | Path to your blocks directory |
| `BLOXCUE_MAX_TOKENS` | `3000` | Default token budget for `inject_context` |
| `BLOXCUE_DATABASE_URL` | *(none)* | PostgreSQL connection URL |
| `BLOXCUE_PG_ENABLED` | `1` | Set to `0` to disable PG even with a URL |
| `BLOXCUE_PG_CACHE_TTL` | `300` | Seconds before PG learnings are re-fetched |
| `DATABASE_URL` | *(none)* | Fallback PG URL (if `BLOXCUE_DATABASE_URL` not set) |

### Example: Full MCP config with PostgreSQL

```json
{
  "mcpServers": {
    "bloxcue": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/user/bloxcue/scripts/mcp_server.py"],
      "env": {
        "BLOXCUE_DATABASE_URL": "postgresql://user:pass@localhost:5432/mydb",
        "BLOXCUE_MEMORY_DIR": "/home/user/bloxcue",
        "BLOXCUE_MAX_TOKENS": "4000",
        "BLOXCUE_PG_CACHE_TTL": "600"
      }
    }
  }
}
```

---

## Best Practices

1. **Keep CLAUDE.md minimal** - Just essentials, let blocks handle details
2. **One topic per file** - Better search precision
3. **Use frontmatter** - Title, category, and tags improve indexing
4. **Use descriptive tags** - `[deployment, production, aws]` not just `[deploy]`
5. **Re-index after changes** - Run the indexer after adding/editing files
6. **Use `inject_context` over `search_blocks` + `get_block`** - One call, token-budgeted, deduplicated
7. **Enable PostgreSQL** if using Continuous-Claude - Unified search across files and learnings

---

## FAQ

<details>
<summary><strong>Do I need Continuous-Claude?</strong></summary>

Technically no, but recommended. Continuous-Claude handles session memory, BloxCue handles knowledge retrieval. They complement each other. With PG integration, BloxCue can search both.
</details>

<details>
<summary><strong>Will this work with Cursor/VS Code/Windsurf?</strong></summary>

Yes! The MCP server works with **any MCP-compatible client**. The hook-based auto-retrieval is specific to Claude Code CLI, but the MCP tools work everywhere.
</details>

<details>
<summary><strong>How is this different from a smaller CLAUDE.md?</strong></summary>

Three key differences:
1. **Scalability** - Your knowledge grows without growing token usage
2. **Relevance** - Only blocks matching your query get loaded
3. **Intelligence** - BM25 ranking, intent detection, and token budgeting beat naive loading
</details>

<details>
<summary><strong>What if Claude needs multiple blocks?</strong></summary>

`inject_context` handles this automatically. It returns multiple blocks ranked by relevance, with smart token budgeting: full content for top results, summaries for mid-range, and references for the rest.
</details>

<details>
<summary><strong>Can I use project-specific docs?</strong></summary>

Yes! You can have both:
- Global: `~/.claude-memory/` for cross-project content
- Project: `./claude-memory/` for project-specific docs

The installer supports setting up both.
</details>

<details>
<summary><strong>Do I need psycopg2 for PostgreSQL?</strong></summary>

Yes, but it's **completely optional**. Without `psycopg2`, BloxCue works identically to before - pure Python, zero dependencies. Install it only if you want PG integration:

```bash
pip install psycopg2-binary
```
</details>

<details>
<summary><strong>How do I back up my blocks?</strong></summary>

They're just markdown files. Back them up however you prefer:
- Git repo (recommended)
- Cloud sync (Dropbox, iCloud, etc.)
- Any backup solution you use
</details>

<details>
<summary><strong>What's the difference between v1 and v2?</strong></summary>

| Aspect | v1 | v2 |
|--------|----|----|
| Search | Keyword matching | BM25 + IDF + stemming + intent detection |
| Interface | CLI + shell hook | CLI + shell hook + **MCP server (6 tools)** |
| Data sources | Markdown files | Markdown files + **PostgreSQL** |
| Context injection | Dump full files | **Token-budgeted** (full/summary/reference tiers) |
| Tests | None | **245+ unit tests** |
</details>

---

## Troubleshooting

### "Command not found: python3"

```bash
# macOS
brew install python3

# Ubuntu/Debian
sudo apt install python3
```

### "No results found" when searching

1. Run the indexer: `python3 ~/.claude-memory/scripts/indexer.py`
2. Check files have `.md` extension
3. Verify files are in the correct directory

### Hook not triggering

1. Check `~/.claude/settings.json` syntax (valid JSON?)
2. Verify the hook path is correct
3. Restart Claude Code after changing settings

### MCP server not connecting

1. Verify the path in your `mcp_config.json` is absolute
2. Check stderr output: `python3 /path/to/mcp_server.py 2>&1`
3. Ensure Python 3.8+ is on the MCP command's PATH

### PostgreSQL not showing in results

1. Verify `BLOXCUE_DATABASE_URL` is set correctly
2. Check `psycopg2` is installed: `python3 -c "import psycopg2"`
3. Rebuild the index: call `index_blocks` via MCP or run the CLI indexer
4. Check server startup logs for `PostgreSQL integration: enabled`

---

## Security

BloxCue is designed with security in mind:

| Protection | Description |
|------------|-------------|
| **Local-only** | No telemetry, no data collection |
| **Path validation** | Prevents directory traversal attacks |
| **Input sanitization** | User prompts are sanitized before processing |
| **Type safety** | Handles malformed data gracefully without crashes |
| **Settings backup** | Creates backup before modifying Claude config |
| **File locking** | Exclusive locks prevent index corruption from concurrent sessions |
| **Read-only DB** | PostgreSQL connections use `readonly=True` - BloxCue never writes to your DB |
| **Optional deps** | `psycopg2` failure is non-fatal; core always works |

See [SECURITY.md](SECURITY.md) for the full security audit report.

---

## Roadmap

- [x] Porter Stemmer for word normalization
- [x] IDF weighting for term importance
- [x] Bigram/phrase matching
- [x] Query intent detection
- [x] Synonym expansion (50+ tech terms)
- [x] BM25 probabilistic ranking
- [x] MMR diversity in results
- [x] Token-budgeted context injection
- [x] Path traversal protection
- [x] Type safety hardening
- [x] Stemmer memoization (LRU cache)
- [x] Index caching with mtime invalidation
- [x] File locking for concurrent safety
- [x] MCP server (6 tools)
- [x] PostgreSQL integration (Continuous-Claude learnings)
- [x] 245+ unit tests
- [ ] Semantic search with embeddings
- [ ] VS Code extension for block management
- [ ] Web UI for managing memory
- [ ] Cross-machine sync

---

## Contributing

Ideas and contributions welcome! See the roadmap above for planned features.

---

## Credits

- [parcadei](https://github.com/parcadei) - Creator of [Continuous-Claude v3](https://github.com/parcadei/Continuous-Claude-v3)

---

## License

MIT - Use it however you want.

---

<p align="center">
  Made by <a href="https://github.com/bokiko">@bokiko</a> · <a href="https://twitter.com/bokiko">Twitter</a> · <a href="https://bokiko.io">bokiko.io</a>
</p>
