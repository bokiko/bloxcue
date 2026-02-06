# BloxCue Security Audit Remediation

**Date:** 2026-02-06
**Scope:** Independent security audit findings — 2 critical, 2 medium, 4 low

---

## Summary

All 8 identified vulnerabilities have been remediated across 4 files.

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| CVE-1 | Critical | Command injection in hook via `$()` / backticks | Fixed |
| CVE-2 | Critical | Code injection via heredoc string escape | Fixed |
| M-1 | Medium | Path traversal prefix bypass in indexer | Fixed |
| M-2 | Medium | Unbounded limit/max_tokens in MCP server | Fixed |
| L-1 | Low | `int()` ValueError on bad env vars | Fixed |
| L-2 | Low | Exception message disclosure to MCP clients | Fixed |
| L-3 | Low | Bare `except:` clauses in indexer | Fixed |
| L-4 | Low | Folder name injection in installer | Fixed |

---

## Detailed Findings and Fixes

### CVE-1: Command Injection in Hook (Critical)

**File:** `hooks/memory-retrieve.sh`
**Vector:** `USER_MESSAGE` from user prompt was passed as a shell argument to `python3 indexer.py --search "$USER_MESSAGE"`. Bash expands `$(...)` and backticks inside double quotes, so a prompt containing `$(id)` would execute before the indexer ran. The existing Python sanitization stripped control characters but did not strip `$`, backticks, `()`, etc.

**Fix:** Added `tr -d` to strip shell metacharacters (`$`, backticks, `()`, `;&|`, `\`, `'`, `{}`) from `USER_MESSAGE` immediately after Python extraction. This is defense-in-depth — the search query loses these characters but retains all alphanumeric content for matching.

### CVE-2: Code Injection via Heredoc (Critical)

**File:** `hooks/memory-retrieve.sh`
**Vector:** `SEARCH_RESULTS` (JSON containing block content from user-created markdown files) was interpolated into a Python triple-quoted string via heredoc: `results = json.loads('''$SEARCH_RESULTS''')`. If any indexed block contained `'''`, it would break the Python string literal and allow arbitrary code execution.

**Fix:** Replaced heredoc with stdin piping: `echo "$SEARCH_RESULTS" | python3 -c "..."` with `json.load(sys.stdin)`. The JSON never enters the Python source code.

### M-1: Path Traversal Prefix Bypass (Medium)

**File:** `scripts/indexer.py` (2 locations)
**Vector:** Path validation used `str(resolved_path).startswith(str(memory_dir_resolved))`. A sibling directory like `/home/user/.claude-memory-evil` would pass the check when `MEMORY_DIR` is `/home/user/.claude-memory` because the string prefix matches.

**Fix:** Changed to `startswith(base + os.sep)` with an exact-match check for the base directory itself. Now `/home/user/.claude-memory-evil` is correctly rejected.

### M-2: Unbounded limit/max_tokens (Medium)

**File:** `scripts/mcp_server.py`
**Vector:** `handle_search_blocks` passed `limit` to `indexer.search()` uncapped. `handle_inject_context` passed `max_tokens` uncapped. A malicious MCP client could request extreme values causing resource exhaustion.

**Fix:** Capped `limit` to 100 and `max_tokens` to 50,000 in both handlers.

### L-1: ValueError on Bad Environment Variables (Low)

**File:** `scripts/indexer.py`
**Vector:** `int(os.environ.get("BLOXCUE_MAX_TOKENS", "3000"))` would crash at import time if the env var contained non-numeric text.

**Fix:** Wrapped both `int()` calls in `try/except (ValueError, TypeError)` with sensible defaults.

### L-2: Exception Message Disclosure (Low)

**File:** `scripts/mcp_server.py`
**Vector:** Tool handler exceptions returned `str(e)` to the MCP client, potentially leaking internal file paths and system details.

**Fix:** Full error is now logged to stderr; client receives only `"Internal error executing {tool_name}"`.

### L-3: Bare except Clauses (Low)

**File:** `scripts/indexer.py`
**Vector:** Bare `except:` catches `SystemExit` and `KeyboardInterrupt`, masking real issues and making debugging harder.

**Fix:** Narrowed to `except Exception:` at all locations.

### L-4: Folder Name Injection in Installer (Low)

**File:** `install.sh`
**Vector:** User-provided folder names (options 2 and 6) were passed directly to `mkdir -p` without validation. A name like `../../tmp/evil` would create directories outside the install path.

**Fix:** Added validation rejecting folder names containing `/`, starting with `..` or `.`, or empty strings.

---

## Verification

Each fix was verified:

1. **CVE-1:** `$(id > /tmp/pwned)` sanitized to `id > /tmp/pwned` — no shell expansion possible
2. **CVE-2:** JSON containing `'''` parsed correctly via stdin — no string escape
3. **M-1:** `/a/batch` correctly rejected when base is `/a/b`; `/a/b/file` correctly allowed
4. **M-2:** `limit=999999` capped to 100; `max_tokens=10000000` capped to 50000
5. **L-1:** `BLOXCUE_MAX_TOKENS=abc` falls back to 3000 without crash
6. **L-4:** `../../tmp/evil`, `../hack`, `.secret`, `a/b/c`, and empty strings all rejected

---

## Files Modified

| File | Changes |
|------|---------|
| `hooks/memory-retrieve.sh` | CVE-1: shell metachar sanitization; CVE-2: stdin-based JSON parsing |
| `scripts/indexer.py` | M-1: path traversal fix (2 locations); L-1: safe env parsing; L-3: narrow excepts |
| `scripts/mcp_server.py` | M-2: cap limit/max_tokens; L-2: generic error messages |
| `install.sh` | L-4: folder name validation |
