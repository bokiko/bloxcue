# BloxCue Knowledge Block Templates

Sample markdown blocks you can copy into your `~/.bloxcue/knowledge/` directory as starting points. The installer **does not** copy these automatically — they're standalone references for browsing here on GitHub or copy-pasting selectively.

## Structure

| Path | What's inside | When to use |
|---|---|---|
| [`examples/`](examples/) | Single, well-formed example blocks (API reference, database schema, deployment guide, project overview) | Read these first if you've never written a knowledge block |
| [`by-subject/`](by-subject/) | Topical organization — runbooks, infrastructure, etc. | Mirror this layout if you want to organize by topic across projects |
| [`by-project/`](by-project/) | One folder per project | Mirror this layout if you want to organize by project (e.g., per-client) |

## Block format

Every block is a markdown file with optional YAML frontmatter:

```markdown
---
title: Production Deploy
category: deployment
tags: [deploy, production, aws]
---

# Production Deploy

Step 1. Run tests locally.
Step 2. Apply migrations.
...
```

Frontmatter fields BloxCue uses:

- `title` — shown in search results; falls back to filename
- `category` — used to group blocks; falls back to parent directory name
- `tags` — boost search ranking when query matches a tag

Anything below the frontmatter is the block body, indexed for BM25 search.

## Using a template

```bash
# Copy a template into your knowledge dir
cp templates/examples/deployment-guide.md ~/.bloxcue/knowledge/guides/

# Edit it for your situation
$EDITOR ~/.bloxcue/knowledge/guides/deployment-guide.md

# Re-index so your AI tool can find it
python3 ~/.bloxcue/knowledge/scripts/indexer.py
```

After re-indexing, any MCP-connected client (Claude Code, Codex, Gemini, Cursor, Windsurf) can search and inject the block.
