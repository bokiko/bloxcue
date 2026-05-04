# Security Policy

## Security Reports

All security audits and remediations are documented in [`security/`](security/):

| Date | Report | Findings | Status |
|------|--------|----------|--------|
| 2026-02-06 | [v2 audit remediation](security/2026-02-06-audit-remediation.md) | 2 critical, 2 medium, 4 low | All fixed |
| 2026-05-04 | [v3.0.1 audit remediation](security/2026-05-04-v3-audit-remediation.md) | 2 high, 3 medium, 3 low | All fixed |

We believe in full transparency. If vulnerabilities are found, we
document what they were, how they could be exploited, and exactly how
we fixed them. The 2026-05-04 report includes the symlink indexing
leak that existed in v3.0.0 and the MCP/CLI index split-brain bug —
both shipped in v3.0.0 and were fixed in v3.0.1.

---

## Security Rating: LOW RISK

BloxCue is a local-only context retrieval engine for Claude Code (and
any other MCP-aware client). Core operations happen on your machine
with no external network calls. PostgreSQL is no longer a runtime
integration in v3 — it is a one-time, opt-in import path used to copy
old `archival_memory` rows into BloxCue's local SQLite store.

## What BloxCue Accesses

| Location | Access | Purpose | Component |
|----------|--------|---------|-----------|
| `~/.bloxcue/knowledge/` | Read/Write | Primary knowledge directory (markdown blocks) | Indexer, MCP server |
| `~/.bloxcue/knowledge/.bloxcue/index.json` | Read/Write (atomic rename) | Search index cache | Indexer |
| `~/.bloxcue/knowledge/.bloxcue/usage.jsonl` | Append | Local search analytics for the health report | Indexer |
| `~/.bloxcue/learnings.db` | Read/Write | Local SQLite store for imported learnings | Indexer |
| `~/.claude-memory/` | Read-only | Legacy v2 memory dir, still readable for users mid-migration | Indexer |
| `~/.claude/mcp_config.json` | Read/Write | Register the MCP server. Touched **only** when the user runs `install.sh --claude-hook` | Installer |
| stdin / stdout | Read/Write | JSON-RPC 2.0 over stdio | MCP server |
| stderr | Write | Diagnostic logging only | MCP server, indexer |
| PostgreSQL | Read-only, **one-time** | Importer copies `archival_memory` rows into local SQLite via `--import-postgres` | Indexer importer |

In v3 the runtime PostgreSQL merge that v2 supported is **off**. The
opt-in legacy compatibility flag (`BLOXCUE_ENABLE_LEGACY_PG_RUNTIME=1`)
exists for migration but is not the recommended path.

## Security Guarantees

### Core (always)

- **No network activity** — Core operations are entirely local.
- **No telemetry** — No usage data is collected or transmitted.
- **No external dependencies** — Core uses only the Python standard library.
- **User-controlled data** — Files stay on your machine.
- **MIT License** — Fully transparent, auditable code.
- **Atomic-rename writes** *(new in v3.0.1)* — The index is written to
  a temp file and atomically renamed into place via `os.replace`.
  This is portable across POSIX and Windows. The previous fcntl-based
  scheme had a truncate-before-lock race that could leave a zero-byte
  index on concurrent writes; the new scheme cannot.
- **Symlink rejection at index time** *(new in v3.0.1)* — Before
  `index_file()` reads a markdown file it resolves the path and
  rejects anything that does not land inside an allowed knowledge
  root. This closes the H-1 leak vector where a symlink inside the
  memory dir pointing at an external file would copy that file's
  content into the index `preview`. Symlinks pointing at files
  *inside* the memory dirs remain legitimate.
- **Path validation at retrieval** — `get_file_content()` uses an
  exact-match plus `os.sep` suffix check against allowed roots,
  preventing both path traversal and prefix-bypass attacks.
- **Input sanitization** — Search queries pass through stemming and
  stopword filtering; the Claude Code hook strips control bytes
  before forwarding the prompt.
- **Type safety** — Malformed frontmatter, malformed index data, and
  malformed tool arguments are caught at boundaries and returned as
  empty results rather than exceptions.
- **Installer no-mutation default** *(new in v3)* — `install.sh`
  creates the knowledge folder and copies `indexer.py`. It does
  **not** modify `~/.claude/mcp_config.json` or any Claude Code
  settings unless the user explicitly passes `--claude-hook`.

### MCP server

- **stdio transport only** — No HTTP server, no open ports, no
  network listeners.
- **JSON-RPC 2.0** — Standard protocol, no custom wire format.
- **Read-only operations for retrieval tools** — `search_blocks`,
  `list_blocks`, `block_health`, and `inject_context` never modify
  files. Index rebuild is explicit (`index_blocks` tool) and only
  happens when called.
- **Error containment** — Tool execution errors return MCP error
  responses with a generic message; the full error is logged to
  stderr only. The server does not crash on bad input.
- **Bounded inputs** — `limit` is capped at 100 and `max_tokens`
  at 50,000 server-side, so a malicious or buggy MCP client cannot
  cause runaway resource use.

### Claude Code hook (`hooks/memory-retrieve.py`)

- **Defense-in-depth sanitization** — User prompts are stripped of
  control characters before being passed to the indexer.
- **Subprocess with `shell=False`** — The indexer is invoked with an
  argv list, not a shell string; shell metacharacters in the prompt
  cannot be expanded.
- **Crash-resistant env parsing** *(new in v3.0.1)* — Garbage values
  in `BLOXCUE_HOOK_MAX_RESULTS`, `BLOXCUE_HOOK_MAX_CONTEXT_CHARS`,
  or `BLOXCUE_HOOK_MIN_QUERY_LENGTH` fall back to defaults instead
  of raising `ValueError` at module import. The hook always emits
  valid JSON, even with a misconfigured environment.
- **Time-bounded** — The indexer subprocess has a 10-second timeout.

### PostgreSQL importer (one-time)

- **Optional** — `psycopg2` is imported in a `try/except`. Without it
  BloxCue runs identically; the `--import-postgres` path is simply
  unavailable.
- **Read-only connections** — All connections use
  `conn.set_session(readonly=True)`. The importer never writes to
  any Postgres database.
- **No runtime merge** — Runtime PG merging from v2 is gone. To stay
  on the v2 behavior temporarily, set
  `BLOXCUE_ENABLE_LEGACY_PG_RUNTIME=1`. This is a migration aid and
  will be removed in v3.1.
- **Connection timeouts** — `connect_timeout=3` (health) /
  `connect_timeout=5` (queries).
- **No credential storage** — Database URLs are passed via env
  (`BLOXCUE_DATABASE_URL` or `DATABASE_URL`); never written to disk.
- **Parameterized queries** — All SQL uses `%s` placeholders.
- **Scoped queries** — Reads only from `archival_memory` with a
  `WHERE metadata->>'type' = 'session_learning'` filter.

## Attack Surface Analysis

| Attack vector | Barrier |
|---------------|---------|
| Modify block files | Filesystem write access to `~/.bloxcue/knowledge/` |
| Tamper with index | Filesystem write access to `~/.bloxcue/knowledge/.bloxcue/index.json` |
| Inject via MCP | Control of the stdio pipe (process-level access) |
| SQL injection (importer) | Control of `BLOXCUE_DATABASE_URL` (shell access) |
| Path traversal at retrieval | Blocked by `Path.resolve()` + `os.sep`-suffix check |
| **Symlink leak at indexing** | *(closed in v3.0.1)* Now blocked by the same check at index time |

All attack vectors require existing local access. BloxCue is not the
weakest link in any threat model that involves filesystem write
access to the user's home directory.

## Installation Safety

`install.sh`:

1. Creates `~/.bloxcue/knowledge/` and copies `indexer.py` and
   `mcp_server.py` into the `scripts/` subdirectory.
2. Prints MCP setup instructions for Claude Code, Cursor, Windsurf,
   etc.
3. **Does not** modify `~/.claude/mcp_config.json` or
   `~/.claude/settings.json` by default.
4. Adds the Claude Code retrieval hook only when invoked with
   `--claude-hook`.
5. Validates folder names provided to interactive prompts (rejects
   `/`, leading `.` or `..`, and empty strings).
6. Does not require elevated privileges and never makes network
   requests.

## Component-by-Component Audit

### 1. Installer (`install.sh`) — SAFE

- Creates `~/.bloxcue/knowledge/` and the `scripts/` subdirectory.
- Touches `~/.claude/mcp_config.json` **only** when the user passes
  `--claude-hook` (v3 default is no mutation).
- Folder name validation rejects path traversal attempts.
- No network requests, no credential collection.

### 2. Indexer (`scripts/indexer.py`) — SAFE

- Reads markdown files from `BLOXCUE_MEMORY_DIR` (default
  `~/.bloxcue/knowledge/`) and the read-only legacy
  `~/.claude-memory/` if present.
- Symlinks resolving outside allowed roots are rejected at index
  time *(v3.0.1)*.
- Index and usage logs are written under
  `MEMORY_DIR/.bloxcue/` *(v3.0.1)* using atomic rename — no
  truncate-before-lock race, no fcntl, Windows-portable.
- Path validation (`os.sep`-suffix prefix check) on retrieval.
- Sanitizes search input via stemming and stopword filtering.
- Safe parsing for `BLOXCUE_MAX_TOKENS` and friends — bad values
  fall back to defaults.

### 3. MCP server (`scripts/mcp_server.py`) — SAFE

- Communicates over stdin/stdout only, no listeners.
- Delegates all reads/writes to `indexer.py` and inherits its
  protections.
- Bounded `limit` and `max_tokens` in tool handlers.
- Generic error messages to clients; full detail to stderr.

### 4. PostgreSQL provider (`scripts/pg_provider.py`) — SAFE (when used)

- `psycopg2` import is optional.
- Connections are read-only.
- Used only by the `--import-postgres` migration path; not on the
  hot path.

### 5. Claude Code hook (`hooks/memory-retrieve.py`) — SAFE

- Triggered on `UserPromptSubmit`, runs in Claude Code's controlled
  environment.
- `shell=False` subprocess with argv list — shell metacharacters in
  prompts cannot be expanded.
- Crash-resistant env parsing *(v3.0.1)* — bad
  `BLOXCUE_HOOK_*` values fall back to defaults; the hook always
  emits valid JSON.
- 10-second timeout on the indexer subprocess.

### 6. Network security

| Component | Network activity |
|-----------|------------------|
| Indexer | None |
| MCP server | None (stdio only) |
| Claude Code hook | None |
| PG importer | localhost DB connection only, when invoked |
| Installer | None |

### 7. Data privacy

- All markdown blocks stored locally.
- Search index and usage log stored locally under
  `~/.bloxcue/knowledge/.bloxcue/`.
- No analytics, telemetry, or external transmission.
- PostgreSQL connections (importer only) are read-only; no user
  data is ever written to a database.

## Vulnerability Assessment

| Date | Version | Source | Findings | Status |
|------|---------|--------|----------|--------|
| 2026-02-06 | v2.0 | Independent security audit | 2 critical, 2 medium, 4 low | All fixed |
| 2026-05-04 | v3.0.1 | External code audit (Codex) | 2 high (symlink indexing leak, MCP/CLI index split-brain), 3 medium (truncate-before-lock race, hook env crash, stale security docs), 3 low (shellcheck warnings, CLI limit validation, PG import idempotency) | All fixed in v3.0.1 |

**Open vulnerabilities: 0**

The 2026-05-04 audit found two High-severity bugs that shipped in
v3.0.0:

- **Symlink indexing leak** — A symlink under
  `~/.bloxcue/knowledge/` pointing at an external file would have
  its content read into the index `preview` field. Existed in
  v3.0.0; fixed in v3.0.1.
- **MCP/CLI index split-brain** — The MCP server and the installed
  CLI wrote to different `.index.json` files because both defaulted
  the path to their own `SCRIPT_DIR`. Existed in v3.0.0; fixed in
  v3.0.1.

Full details, exploit conditions, and per-finding tests:
[`security/2026-05-04-v3-audit-remediation.md`](security/2026-05-04-v3-audit-remediation.md).

## Security Checklist

- [x] No malicious code detected
- [x] No network exfiltration
- [x] No credential harvesting
- [x] No unauthorized file access
- [x] Local operations only (core)
- [x] MIT License (transparent)
- [x] Input validation implemented
- [x] Path traversal protection at retrieval
- [x] Symlink rejection at indexing *(v3.0.1)*
- [x] Atomic-rename index writes *(v3.0.1)*
- [x] Cross-platform (no fcntl) *(v3.0.1)*
- [x] Crash-resistant env parsing in hook *(v3.0.1)*
- [x] SQL injection prevention (parameterized queries)
- [x] Error handling (non-crashing)
- [x] Read-only Postgres connections (importer)
- [x] Connection timeouts on all DB calls
- [x] Graceful degradation when optional deps are missing
- [x] No credentials stored on disk
- [x] Installer is non-mutating by default *(v3)*

## Reporting Vulnerabilities

If you discover a security issue, please:

1. **Do not** open a public GitHub issue.
2. Email the maintainer directly.
3. Allow 90 days for a fix before public disclosure.

## Audit History

| Date | Version | Auditor | Findings | Result |
|------|---------|---------|----------|--------|
| 2025-01-01 | v1.0 | Automated security analysis + Corridor | None | Safe |
| 2026-02-06 | v2.0 | Independent security audit | 8 issues (2C / 2M / 4L) | All remediated same day, see [report](security/2026-02-06-audit-remediation.md) |
| 2026-05-04 | v3.0.1 | External code audit (Codex) | 8 issues (2H / 3M / 3L) | All remediated, see [report](security/2026-05-04-v3-audit-remediation.md) |

---

*Last security review: 2026-05-04*
