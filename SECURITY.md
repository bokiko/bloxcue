# Security Policy

## Security Rating: LOW RISK

BloxCue is a **local-only** context retrieval engine for Claude Code. Core operations happen on your machine with no external dependencies. The optional PostgreSQL integration connects only to a user-configured local database.

## What BloxCue Accesses

| Location | Access | Purpose | Component |
|----------|--------|---------|-----------|
| `~/.claude-memory/` | Read/Write | Store and index your context blocks | Indexer |
| `~/.claude/settings.json` | Read/Write | Register the retrieval hook | Installer |
| `~/.claude/hooks/` | Write | Install the hook script | Installer |
| `scripts/.index.json` | Read/Write | Search index cache | Indexer |
| `scripts/.usage.jsonl` | Append | Search usage analytics (local only) | Indexer |
| `stdin/stdout` | Read/Write | JSON-RPC messages over stdio | MCP Server |
| `stderr` | Write | Diagnostic logging | MCP Server |
| PostgreSQL (optional) | **Read-only** | Fetch learnings from `archival_memory` | PG Provider |

## Security Guarantees

### Core (Always)

- **No network activity** - Core operations are entirely local
- **No telemetry** - No usage data collected or transmitted
- **No external dependencies** - Core uses only Python standard library
- **User-controlled data** - All files stay on your machine
- **MIT License** - Fully transparent, auditable code
- **File locking** - Exclusive locks prevent index corruption from concurrent access
- **Path validation** - Directory traversal attacks are blocked in all file operations
- **Input sanitization** - Search queries are sanitized before processing
- **Type safety** - Malformed frontmatter, index data, and tool arguments are handled gracefully

### MCP Server

- **stdio transport only** - No HTTP server, no open ports, no network listeners
- **JSON-RPC 2.0** - Standard protocol, no custom wire format
- **Read-only operations** - Search, list, and health tools never modify files
- **Index rebuild is explicit** - Only `index_blocks` modifies the index, and only when called
- **Error containment** - Tool execution errors return MCP error responses, never crash the server

### PostgreSQL Integration (Optional)

- **Completely optional** - `psycopg2` is imported in a `try/except`. Without it, BloxCue behaves identically to v1.
- **Kill switch** - Set `BLOXCUE_PG_ENABLED=0` to disable even if a database URL is configured.
- **Read-only connections** - All connections use `conn.set_session(readonly=True)`. BloxCue never writes to, modifies, or deletes any database records.
- **Non-fatal errors** - Every database call is wrapped in `try/except`. PG failures are logged to stderr; file search always works.
- **Connection timeouts** - All connections use `connect_timeout=3` (health check) or `connect_timeout=5` (queries) to avoid hanging.
- **No credential storage** - Database URLs are passed via environment variables only, never written to disk.
- **Parameterized queries** - All SQL queries use `%s` parameter placeholders, preventing SQL injection.
- **Scoped queries** - Only reads from `archival_memory` table with `WHERE metadata->>'type' = 'session_learning'` filter.

## Attack Surface Analysis

### What an attacker would need

| Attack Vector | Barrier |
|---------------|---------|
| Modify block files | Filesystem access to `~/.claude-memory/` |
| Tamper with index | Filesystem access to `scripts/.index.json` |
| Inject via MCP | Control of the stdio pipe (requires process-level access) |
| SQL injection | Control of environment variables (requires shell access) |
| Path traversal | Blocked by `resolve()` + prefix check in `get_file_content()` |

**Summary:** All attack vectors require existing local access to the user's machine, at which point BloxCue is not the weakest link.

## Installation Safety

The `install.sh` script:
1. Creates backup of `settings.json` before modification
2. Only writes to user-controlled directories
3. Validates paths before file operations
4. Does not require elevated privileges
5. Does not download anything from the internet

## Component-by-Component Audit

### 1. Installation Script (`install.sh`)

**Security Status: SAFE**

- Creates `~/.claude-memory/` directory structure
- Modifies `~/.claude/settings.json` to add hooks
- Creates backup before modifying settings
- No network requests during installation
- No credential collection

### 2. Python Indexer (`scripts/indexer.py`)

**Security Status: SAFE**

- Reads markdown files from configured `MEMORY_DIR` only
- Creates local index file with exclusive file locking
- Implements path validation to prevent directory traversal
- Sanitizes search input through stemming and stopword filtering
- Uses only Python standard library
- Environment variable configuration has safe defaults

### 3. MCP Server (`scripts/mcp_server.py`)

**Security Status: SAFE**

- Communicates via stdin/stdout only (no network listeners)
- Delegates all operations to `indexer.py` (inherits its protections)
- Invalid JSON-RPC messages return error responses, not crashes
- Unknown methods return `-32601` errors per JSON-RPC spec
- Tool arguments are validated before use

### 4. PostgreSQL Provider (`scripts/pg_provider.py`)

**Security Status: SAFE (when enabled)**

- `psycopg2` imported in try/except - missing module is graceful
- All connections are read-only (`set_session(readonly=True)`)
- All queries use parameterized placeholders (no string interpolation)
- Connection failures return empty results, not exceptions
- Only accesses `archival_memory` table with explicit type filter
- Learning IDs are passed as query parameters, not interpolated
- No credentials stored in code or on disk

### 5. Hook Script (`hooks/memory-retrieve.sh`)

**Security Status: SAFE**

- Triggered on `UserPromptSubmit` event
- Calls `indexer.py` to find relevant blocks
- Runs in Claude Code's controlled environment
- No network activity
- Input properly sanitized before processing

### 6. Network Security

**Status: NO UNAUTHORIZED NETWORK ACTIVITY**

| Component | Network Activity |
|-----------|-----------------|
| Indexer | None |
| MCP Server | None (stdio only) |
| Hook Script | None |
| PG Provider | localhost DB connection only (user-configured) |
| Install Script | None |

### 7. Data Privacy

- All markdown blocks stored locally
- Search index stored locally
- Usage log stored locally (append-only JSONL)
- No data collection, analytics, or tracking
- PostgreSQL queries are read-only; no user data is written to any database
- Database URLs exist only in environment variables

## Vulnerability Assessment

| Severity | Count | Details |
|----------|-------|---------|
| Critical | 0 | None |
| High | 0 | None |
| Medium | 0 | Path traversal and SQL injection mitigated |
| Low | 0 | All recommendations implemented |

## Security Checklist

- [x] No malicious code detected
- [x] No network exfiltration
- [x] No credential harvesting
- [x] No unauthorized file access
- [x] Local operations only (core)
- [x] MIT License (transparent)
- [x] Input validation implemented
- [x] Path traversal protection
- [x] SQL injection prevention (parameterized queries)
- [x] Settings backup mechanism
- [x] Error handling (non-crashing)
- [x] File locking for concurrent safety
- [x] Read-only database connections
- [x] Connection timeouts on all DB calls
- [x] Graceful degradation when optional deps missing
- [x] No credentials stored on disk

## Reporting Vulnerabilities

If you discover a security issue, please:
1. **Do not** open a public GitHub issue
2. Email the maintainer directly
3. Allow 90 days for a fix before public disclosure

## Audit History

| Date | Version | Auditor | Result |
|------|---------|---------|--------|
| 2025-01-01 | v1.0 | Automated Security Analysis + Corridor | SAFE |
| 2026-02-06 | v2.0 | Manual audit (MCP + PG integration) | SAFE |

---

*Last security review: 2026-02-06*
