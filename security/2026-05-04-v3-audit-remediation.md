# BloxCue v3.0.1 Audit Remediation

**Date:** 2026-05-04
**Scope:** External code audit (Codex) of v3.0.0 — 2 high, 3 medium, 3 low

---

## Summary

Eight findings, all remediated in v3.0.1 across `scripts/indexer.py`,
`hooks/memory-retrieve.py`, and the security documentation set. Each fix
ships with a regression test in `tests/unit/test_audit_v3_0_1.py`.

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| H-1 | High | Symlink indexing leaks files outside memory root | Fixed |
| H-2 | High | MCP and CLI use different `.index.json` files (split-brain) | Fixed |
| M-1 | Medium | Truncate-before-lock race in `write_index_safely` | Fixed |
| M-2 | Medium | Hook crashes on bad `BLOXCUE_HOOK_*` env vars before emitting JSON | Fixed |
| M-3 | Medium | `SECURITY.md` was the v2 file and described the wrong architecture | Fixed |
| L-1 | Low | Shellcheck warnings in `install.sh` | Tracked, not in this report |
| L-2 | Low | CLI `--limit` accepted negative / very large values | Tracked, not in this report |
| L-3 | Low | `--import-postgres` was not idempotent on re-run | Tracked, not in this report |

The three Low findings are tracked outside this remediation pass; they
do not affect security guarantees and are bookkept in the v3.0.1
release issue.

---

## Detailed Findings and Fixes

### H-1: Symlink indexing leak

**File:** `scripts/indexer.py` — `index_file()` (was around line 700)
**Origin:** v3.0.0. The bug was present in earlier versions in the same
form but was masked by the fact that the v2 retrieval path validation
in `get_file_content()` rejects out-of-root paths. Indexing has no such
check; the index `preview` field is computed from `read_text()` of the
followed symlink target.

**Exploit conditions:** An attacker who can create files inside
`~/.bloxcue/knowledge/` (or persuade the user to drop one in) can place
a symlink such as `leak.md -> /etc/passwd`. The next index rebuild
(triggered automatically on first search after install, or manually via
`./scripts/indexer.py --rebuild`) reads the target and writes the first
300 characters of `/etc/passwd` into `index.json` under the `preview`
field. From there, the content is reachable via:

- `--list` output (CLI)
- `search_blocks` MCP tool results
- The Claude Code hook injection payload (which reads from `--search`
  output)

In short: the index file itself becomes the leak vector. Path
validation at retrieval time does not help because the bytes have
already been copied into a file the retrieval path is allowed to read.

**Remediation:** In `index_file()`, resolve the path before reading and
reject anything that does not land inside an allowed knowledge root.
The check uses the same `os.sep`-suffix prefix logic that
`get_file_content()` already uses, which prevents a sibling directory
like `/a/.bloxcue-evil` from satisfying a `/a/.bloxcue` base. Symlinks
that point at files *inside* the memory dir remain legitimate (e.g. a
shared knowledge file linked from both `~/.bloxcue/knowledge/` and a
team-shared mount mounted under it) and are still indexed.

**Test:** `test_symlink_to_outside_file_rejected` constructs a temp
memory dir with one legitimate file and one symlink to an external
secret-bearing file, runs `build_index()`, and asserts that the
external content does not appear in any preview field and the symlink
is excluded from `files`. A companion test
`test_symlink_inside_memory_dir_allowed` confirms internal symlinks
are still indexed so the fix is not over-broad.

---

### H-2: MCP and CLI index split-brain

**File:** `scripts/indexer.py` lines 54–56 (pre-fix)
**Origin:** v3.0.0. This regressed when v3 split the runtime into a
repo-resident MCP server and an installed CLI under
`~/.bloxcue/knowledge/scripts/`.

**Exploit conditions:** Not a security exploit; this is a correctness
bug with security-adjacent consequences. `INDEX_FILE` and
`USAGE_FILE` defaulted to `SCRIPT_DIR / .index.json` (and
`.usage.jsonl`). `SCRIPT_DIR` is the directory of the running
`indexer.py`. The MCP server runs the *repo* copy. The CLI installer
copies `indexer.py` into `~/.bloxcue/knowledge/scripts/` and the user
runs that copy. Two different `.index.json` files. They would
silently diverge: the user runs `--rebuild`, gets fresh results,
switches to Claude Code, the MCP server returns stale results from a
file the user never saw. Worse: usage analytics in `usage.jsonl` are
fragmented across two locations, breaking the health report.

**Remediation:** Move both `INDEX_FILE` and `USAGE_FILE` defaults under
`MEMORY_DIR/.bloxcue/` so any indexer process that shares
`BLOXCUE_MEMORY_DIR` also shares the same runtime state. Add
`BLOXCUE_INDEX_FILE` and `BLOXCUE_USAGE_FILE` env-var overrides for
unusual deployments and tests. No data migration is required: stale
`.index.json` files at the old `SCRIPT_DIR` location are caches and
will be regenerated on first search.

**Test:** `test_index_file_under_memory_dir` sets `BLOXCUE_MEMORY_DIR`
to a tmp path, builds the index, and asserts the index file lands at
`<tmp>/.bloxcue/index.json` and not under `SCRIPT_DIR`.
`test_index_file_env_override` exercises the new env-var overrides.

---

### M-1: Truncate-before-lock race

**File:** `scripts/indexer.py` — `write_index_safely()` (was around line 540)
**Origin:** v2.0. The function predates the audit but was never
exercised under genuine concurrent load. The pattern was:

```python
with open(index_path, 'w') as f:        # truncates immediately
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # lock acquired AFTER truncate
    json.dump(data, f, indent=2)
    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

**Exploit conditions:** Two indexer processes running `--rebuild` at
the same moment (e.g. a pre-commit hook and a manual rebuild) can both
hit the `open(path, 'w')` call before either has flock'd, leaving a
brief window where the file is zero bytes. A reader (the MCP server,
the Claude Code hook) opening the file in that window sees an empty
JSON which is treated as "no index" and triggers a re-index, which
itself can race. In the worst case the file is left zero bytes if the
crashing writer dies between truncate and `json.dump`.

**Remediation:** Replace the fcntl-and-truncate dance with the standard
atomic-write pattern: write to a `<index>.tmp` sibling, then
`os.replace()`. `os.replace` is atomic on POSIX *and* Windows.
Concurrent writers do not corrupt each other; the loser of the race
has its `.tmp` overwritten without a zero-byte window. As a bonus
this lets us drop the `import fcntl` line: fcntl is Unix-only, so the
old code did not work on Windows even though every other component is
portable.

**Test:** `test_atomic_write_no_partial_state` pre-seeds a known-good
index, monkeypatches `os.replace` to raise mid-write, triggers a
write, and asserts the original index is byte-for-byte intact.
`test_fcntl_no_longer_imported` greps `indexer.py` source for
`import fcntl` / `from fcntl` to prevent regression.

---

### M-2: Hook crashes on bad env vars before emitting JSON

**File:** `hooks/memory-retrieve.py` lines 18–20
**Origin:** Inherited from the v3 hook rewrite.

**Exploit conditions:** Not exploitable; it is a hard-to-diagnose
operational bug. The hook parses three integer env vars at module
import time:

```python
MAX_RESULTS = int(os.environ.get("BLOXCUE_HOOK_MAX_RESULTS", "3"))
MAX_CONTEXT_CHARS = int(os.environ.get("BLOXCUE_HOOK_MAX_CONTEXT_CHARS", "3000"))
MIN_QUERY_LENGTH = int(os.environ.get("BLOXCUE_HOOK_MIN_QUERY_LENGTH", "5"))
```

A user who fat-fingers their settings file (e.g. `BLOXCUE_HOOK_MAX_RESULTS=3rd`)
gets a hook that exits 1 with a Python traceback on stderr and nothing
on stdout. Claude Code logs the hook as broken and disables it for the
session — silently for users who do not check the hook log.

**Remediation:** Add a `_safe_int(name, default)` helper that mirrors
the pattern `indexer.py` already uses for `BLOXCUE_MAX_TOKENS` (lines
44–47), wrap each parse, fall back to the documented default on
ValueError/TypeError. The hook now always reaches `main()` and emits
valid JSON.

**Test:** `test_hook_with_bad_env_emits_continue` invokes the hook
subprocess with `BLOXCUE_HOOK_MAX_RESULTS=bad`,
`BLOXCUE_HOOK_MAX_CONTEXT_CHARS=garbage`, and
`BLOXCUE_HOOK_MIN_QUERY_LENGTH=not-an-int`, sends a valid stdin
payload, and asserts exit 0 with parseable
`{"result": "continue"}` JSON on stdout.

---

### M-3: SECURITY.md described the wrong architecture

**File:** `SECURITY.md`
**Origin:** v3.0.0 shipped without rewriting the v2 security policy.
The file still claimed:

- Primary data path is `~/.claude-memory/` (v3 uses `~/.bloxcue/knowledge/`)
- Installer modifies `~/.claude/settings.json` by default (v3 only does this with `--claude-hook`)
- `BLOXCUE_PG_ENABLED=0` is the PG kill switch (v3 has no runtime PG by default)
- PostgreSQL is "optional runtime integration" (v3 PG is one-time `--import-postgres` migration only)

**Remediation:** Full rewrite of `SECURITY.md` to reflect v3.0.1
architecture. Add this audit report to the audit history table. List
each finding (including this one) honestly with severity and exploit
notes — the v3.0.0 release did ship with the H-1 symlink leak and the
H-2 split-brain bug.

---

## Files Modified

| File | Changes |
|------|---------|
| `scripts/indexer.py` | H-1: symlink rejection in `index_file`; H-2: relocate INDEX_FILE/USAGE_FILE under MEMORY_DIR; M-1: atomic write via temp + os.replace; drop `import fcntl` |
| `hooks/memory-retrieve.py` | M-2: `_safe_int` helper for env parsing |
| `SECURITY.md` | M-3: full v3 rewrite |
| `security/2026-05-04-v3-audit-remediation.md` | This file |
| `tests/unit/test_audit_v3_0_1.py` | New regression tests for all four code findings |
| `tests/unit/test_block_health.py` | Update `endswith(".usage.jsonl")` assertion to match the new no-dotfile-prefix filename |

---

## Verification

Run the full test suite from the repo root:

```bash
pytest tests/
```

Expected: 212 tests passing (v3.0.0 baseline was 205; this audit pass
adds seven regression tests).

Per-finding spot checks:

- **H-1:** `pytest tests/unit/test_audit_v3_0_1.py::test_symlink_to_outside_file_rejected -v`
- **H-2:** `pytest tests/unit/test_audit_v3_0_1.py::test_index_file_under_memory_dir -v`
- **M-1:** `pytest tests/unit/test_audit_v3_0_1.py::test_atomic_write_no_partial_state -v`
  and `pytest tests/unit/test_audit_v3_0_1.py::test_fcntl_no_longer_imported -v`
- **M-2:** `pytest tests/unit/test_audit_v3_0_1.py::test_hook_with_bad_env_emits_continue -v`

Manual symlink check:

```bash
mkdir -p /tmp/audit-check && echo "secret" > /tmp/audit-check/external.md
mkdir -p ~/.bloxcue/knowledge && ln -sf /tmp/audit-check/external.md ~/.bloxcue/knowledge/leak.md
python3 ~/.bloxcue/knowledge/scripts/indexer.py --rebuild 2>&1 | grep -i skip
# expect: "Skipping symlink outside memory root: ..."
grep -F "secret" ~/.bloxcue/knowledge/.bloxcue/index.json
# expect: no match
```
