<div align="center">

# BloxCue

<h3>Intelligent context blocks for Claude Code. Load what you need, when you need it.</h3>

<p>
  <a href="https://github.com/parcadei/Continuous-Claude-v3">
    <img src="https://img.shields.io/badge/Requires-Continuous--Claude-blue?style=for-the-badge" alt="Requires Continuous-Claude" />
  </a>
</p>

<p>
  <a href="#quick-start">
    <img src="https://img.shields.io/badge/setup-5%20minutes-success" alt="5 min setup" />
  </a>
  <a href="#token-savings">
    <img src="https://img.shields.io/badge/saves-7000+%20tokens%2Fprompt-orange" alt="7000+ tokens saved" />
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
2. [Features](#features)
3. [Who is this for?](#who-is-this-for)
4. [How it works](#how-it-works)
5. [Requirements](#requirements)
6. [Quick Start](#quick-start)
7. [Enable Auto-Retrieval](#enable-auto-retrieval)
8. [After Installation](#after-installation)
9. [For Existing Claude Users](#for-existing-claude-users)
10. [Token Savings](#token-savings)
11. [Directory Structure](#directory-structure)
12. [Commands Reference](#commands-reference)
13. [Best Practices](#best-practices)
14. [FAQ](#faq)
15. [Troubleshooting](#troubleshooting)
16. [Security](#security)
17. [Roadmap](#roadmap)
18. [Contributing](#contributing)
19. [Credits](#credits)

---

## The Story

After using [Continuous-Claude](https://github.com/parcadei/Continuous-Claude-v3) (created by [parcadei](https://github.com/parcadei)), we noticed something: our `CLAUDE.md` files kept growing. Every time we documented something new, added a guide, or saved a configuration, the file got bigger.

**The problem?** Claude loads your entire `CLAUDE.md` on every single prompt. That 30KB file? Loaded 20+ times per session. Hundreds of thousands of tokens wasted on content Claude didn't need.

**Why does this matter?** Whether you're on Claude Pro ($20/month) or Pro Max ($200/month), you have a monthly token budget. Wasting thousands of tokens per prompt on irrelevant context means fewer tokens for actual thinking, coding, and building.

**The solution:** What if Claude could pull in just the context it needs? You ask about your database, Claude grabs the database block. You ask about deployment, Claude grabs the deployment block. Everything else stays on the shelf.

That's **BloxCue** - intelligent context blocks that get loaded when you need them.

---

## Features

### Intelligent Search Engine

BloxCue includes a purpose-built search engine optimized for context retrieval:

| Feature | Description |
|---------|-------------|
| **Porter Stemmer** | Matches word variations (`running` → `run`, `deployment` → `deploy`) |
| **IDF Weighting** | Rare terms rank higher than common ones for better precision |
| **Phrase Matching** | Recognizes multi-word queries like "error handling" as phrases |
| **Query Intent Detection** | Adjusts results based on query type (how-to, troubleshooting, concepts) |
| **Fuzzy Matching** | Finds relevant blocks even with typos or partial matches |
| **Memoized Stemming** | LRU cache on stemmer for 50-70% faster repeated searches |
| **Index Caching** | In-memory cache with mtime checking eliminates repeated disk reads |

### Automatic Context Injection

- Hooks into Claude Code's `UserPromptSubmit` event
- Analyzes your prompt in real-time
- Injects only the most relevant blocks as context
- Zero manual intervention required

### Token Efficiency

- Reduces context loading by ~88%
- Saves ~7,500 tokens per prompt on average
- More tokens available for Claude's reasoning

### Zero Dependencies

- Pure Python standard library - no pip installs required
- No external services or API calls
- Works offline, works anywhere Python 3 runs

---

## Who is this for?

| If you're... | BloxCue helps you... |
|--------------|----------------------|
| **A Claude Code user** | Stop burning tokens on unused context |
| **Managing multiple configs** | Keep docs, guides, and configs organized and searchable |
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
         → Finds deployment block via Porter stemmer
         → IDF weights "production" higher (specific term)
         → Injects only the deployment block

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

If you prefer manual setup, follow our [Continuous-Claude v3](https://github.com/parcadei/Continuous-Claude-v3) first.

> **Credit:** Continuous-Claude was created by [parcadei](https://github.com/parcadei). Check out [Continuous-Claude v3](https://github.com/parcadei/Continuous-Claude-v3).

---

## Quick Start

### Option 1: Let Claude Install (Recommended)

Copy and paste this to Claude:

```
Set up BloxCue for intelligent context management.

1. Clone https://github.com/bokiko/bloxcue to a temp location
2. Run ./install.sh and guide me through the options:
   - Scope: Global, Project, or Both
   - Directory structure preference
3. Set up the auto-retrieval hook in ~/.claude/settings.json
4. Create a sample block to test it works
5. Clean up the cloned repo after install

If I don't have Continuous-Claude yet, set that up first from:
https://github.com/parcadei/Continuous-Claude-v3
```

Claude will handle the technical details while asking for your preferences.

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
└── scripts/
    └── indexer.py      # Search engine
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

---

## Best Practices

1. **Keep CLAUDE.md minimal** - Just essentials, let blocks handle details
2. **One topic per file** - Better search precision
3. **Use frontmatter** - Title, category, and tags improve indexing
4. **Use descriptive tags** - `[deployment, production, aws]` not just `[deploy]`
5. **Re-index after changes** - Run the indexer after adding/editing files

---

## FAQ

<details>
<summary><strong>Do I need Continuous-Claude?</strong></summary>

Technically no, but recommended. Continuous-Claude handles session memory, BloxCue handles knowledge retrieval. They complement each other.
</details>

<details>
<summary><strong>Will this work with Cursor/VS Code?</strong></summary>

Designed for **Claude Code CLI**. May work with other Claude integrations that support hooks, but untested.
</details>

<details>
<summary><strong>How is this different from a smaller CLAUDE.md?</strong></summary>

Two key differences:
1. **Scalability** - Your knowledge grows without growing token usage
2. **Relevance** - Only blocks matching your query get loaded

A smaller CLAUDE.md means less information. BloxCue means the right information at the right time.
</details>

<details>
<summary><strong>What if Claude needs multiple blocks?</strong></summary>

The retrieval hook returns multiple relevant blocks based on keyword matching. A query about "database deployment" may return both the database block and deployment block.
</details>

<details>
<summary><strong>Can I use project-specific docs?</strong></summary>

Yes! You can have both:
- Global: `~/.claude-memory/` for cross-project content
- Project: `./claude-memory/` for project-specific docs

The installer supports setting up both.
</details>

<details>
<summary><strong>How do I back up my blocks?</strong></summary>

They're just markdown files. Back them up however you prefer:
- Git repo (recommended)
- Cloud sync (Dropbox, iCloud, etc.)
- Any backup solution you use
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

---

## Security

BloxCue is designed with security in mind:

| Protection | Description |
|------------|-------------|
| **Local-only** | No network activity, no telemetry, no data collection |
| **Path validation** | Prevents directory traversal attacks |
| **Input sanitization** | User prompts are sanitized before processing |
| **Type safety** | Handles malformed data gracefully without crashes |
| **Settings backup** | Creates backup before modifying Claude config |
| **File locking** | Exclusive locks prevent index corruption from concurrent sessions |

See [SECURITY.md](SECURITY.md) for the full security audit report.

---

## Roadmap

- [x] Porter Stemmer for word normalization
- [x] IDF weighting for term importance
- [x] Bigram/phrase matching
- [x] Query intent detection
- [x] Path traversal protection
- [x] Type safety hardening
- [x] Stemmer memoization (LRU cache)
- [x] Index caching with mtime invalidation
- [x] File locking for concurrent safety
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
