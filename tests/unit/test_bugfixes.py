#!/usr/bin/env python3
"""
Regression tests for bugs found during debug pass.

Bug 1: generate_health_report() crashed with UnboundLocalError when no usage log
Bug 2: load_usage_log() dropped all records after a corrupt JSONL line
Bug 3: search() crashed on non-string queries (None, int)
Bug 4: bm25_score() division by zero when avg_dl=0
Bug 5: MCP handlers leaked internal error details on bad input types
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import indexer
import mcp_server

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}")
        failed += 1


def section(name):
    print(f"\n{name}")
    print("-" * 40)


# ============================================================
# Bug 1: Health report with no usage log
# ============================================================
section("Bug 1: Health report no-usage-log crash")

original_usage = indexer.USAGE_FILE
indexer.USAGE_FILE = SCRIPTS_DIR / ".nonexistent_regtest.jsonl"
try:
    report = indexer.generate_health_report()
    check("no_usage_log_no_crash", isinstance(report, str))
    check("no_usage_log_has_title", "Block Health Report" in report)
    check("no_usage_log_has_totals", "Total blocks:" in report)
finally:
    indexer.USAGE_FILE = original_usage


# ============================================================
# Bug 2: Corrupt JSONL recovery
# ============================================================
section("Bug 2: Corrupt JSONL line recovery")

temp_corrupt = SCRIPTS_DIR / ".regtest_corrupt.jsonl"
original_usage2 = indexer.USAGE_FILE
indexer.USAGE_FILE = temp_corrupt
try:
    temp_corrupt.write_text(
        '{"q":"first","hit":true}\n'
        'NOT VALID JSON\n'
        '{"q":"third","hit":false}\n'
    )
    records = indexer.load_usage_log()
    check("corrupt_doesnt_crash", True)
    check("corrupt_recovers_valid_records", len(records) == 2)
    check("corrupt_has_first", records[0]["q"] == "first")
    check("corrupt_has_third", records[1]["q"] == "third")
finally:
    indexer.USAGE_FILE = original_usage2
    if temp_corrupt.exists():
        temp_corrupt.unlink()


# ============================================================
# Bug 3: search() with non-string queries
# ============================================================
section("Bug 3: search() non-string input handling")

check("search_none_returns_empty", indexer.search(None) == [])
check("search_int_returns_empty", indexer.search(123) == [])
check("search_float_returns_empty", indexer.search(3.14) == [])
check("search_list_returns_empty", indexer.search(["test"]) == [])
check("search_empty_returns_empty", indexer.search("") == [])
check("search_whitespace_returns_empty", indexer.search("   ") == [])
check("search_valid_still_works", isinstance(indexer.search("deployment"), list))


# ============================================================
# Bug 4: BM25 division by zero
# ============================================================
section("Bug 4: BM25 avg_dl=0 division by zero")

doc_stats_zero = {"avg_dl": 0, "docs": {"t.md": {"tf": {"x": 3}, "dl": 10}}}
idf_test = {"x": 1.5}

try:
    score = indexer.bm25_score("x", "t.md", doc_stats_zero, idf_test)
    check("bm25_avg_dl_zero_no_crash", True)
    check("bm25_avg_dl_zero_positive", score > 0)
except ZeroDivisionError:
    check("bm25_avg_dl_zero_no_crash", False)
    check("bm25_avg_dl_zero_positive", False)

# Also test with avg_dl=None (from corrupt index)
doc_stats_none = {"avg_dl": None, "docs": {"t.md": {"tf": {"x": 3}, "dl": 10}}}
try:
    score = indexer.bm25_score("x", "t.md", doc_stats_none, idf_test)
    check("bm25_avg_dl_none_no_crash", True)
except Exception:
    check("bm25_avg_dl_none_no_crash", False)


# ============================================================
# Bug 5: MCP input validation
# ============================================================
section("Bug 5: MCP clean error messages")

# search_blocks with integer query
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {"name": "search_blocks", "arguments": {"query": 123}}
})
check("mcp_search_int_is_error", response["result"].get("isError") is True)
error_text = response["result"]["content"][0]["text"]
check("mcp_search_int_clean_msg", "non-empty string" in error_text)
check("mcp_search_int_no_traceback", "attribute" not in error_text.lower())

# inject_context with integer query
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": {"name": "inject_context", "arguments": {"query": 456}}
})
check("mcp_inject_int_is_error", response["result"].get("isError") is True)

# inject_context with bad max_tokens type - should fallback to default
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 3, "method": "tools/call",
    "params": {"name": "inject_context", "arguments": {"query": "test", "max_tokens": "bad"}}
})
check("mcp_inject_bad_tokens_ok", "result" in response)
check("mcp_inject_bad_tokens_not_error", response["result"].get("isError") is not True)

# inject_context with negative max_tokens - should fallback
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 4, "method": "tools/call",
    "params": {"name": "inject_context", "arguments": {"query": "test", "max_tokens": -1}}
})
check("mcp_inject_neg_tokens_ok", "result" in response)


# ============================================================
# Summary
# ============================================================
print(f"\n{'='*60}")
print(f"Results: {passed}/{passed+failed} passed, {failed} failed")

if __name__ == "__main__":
    pass
