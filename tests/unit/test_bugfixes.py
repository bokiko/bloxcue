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
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import indexer
import mcp_server


# ============================================================
# Bug 1: Health report with no usage log
# ============================================================

def test_health_report_no_usage_log_crash():
    """Bug 1: Health report no-usage-log crash."""
    original_usage = indexer.USAGE_FILE
    indexer.USAGE_FILE = SCRIPTS_DIR / ".nonexistent_regtest.jsonl"
    try:
        report = indexer.generate_health_report()
        assert isinstance(report, str), "no_usage_log_no_crash"
        assert "Block Health Report" in report, "no_usage_log_has_title"
        assert "Total blocks:" in report, "no_usage_log_has_totals"
    finally:
        indexer.USAGE_FILE = original_usage


# ============================================================
# Bug 2: Corrupt JSONL recovery
# ============================================================

def test_corrupt_jsonl_recovery():
    """Bug 2: Corrupt JSONL line recovery."""
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
        assert True, "corrupt_doesnt_crash"
        assert len(records) == 2, "corrupt_recovers_valid_records"
        assert records[0]["q"] == "first", "corrupt_has_first"
        assert records[1]["q"] == "third", "corrupt_has_third"
    finally:
        indexer.USAGE_FILE = original_usage2
        if temp_corrupt.exists():
            temp_corrupt.unlink()


# ============================================================
# Bug 3: search() with non-string queries
# ============================================================

def test_search_none_returns_empty():
    assert indexer.search(None) == [], "search_none_returns_empty"


def test_search_int_returns_empty():
    assert indexer.search(123) == [], "search_int_returns_empty"


def test_search_float_returns_empty():
    assert indexer.search(3.14) == [], "search_float_returns_empty"


def test_search_list_returns_empty():
    assert indexer.search(["test"]) == [], "search_list_returns_empty"


def test_search_empty_returns_empty():
    assert indexer.search("") == [], "search_empty_returns_empty"


def test_search_whitespace_returns_empty():
    assert indexer.search("   ") == [], "search_whitespace_returns_empty"


def test_search_valid_still_works():
    assert isinstance(indexer.search("deployment"), list), "search_valid_still_works"


# ============================================================
# Bug 4: BM25 division by zero
# ============================================================

def test_bm25_avg_dl_zero_no_crash():
    """Bug 4: BM25 avg_dl=0 division by zero."""
    doc_stats_zero = {"avg_dl": 0, "docs": {"t.md": {"tf": {"x": 3}, "dl": 10}}}
    idf_test = {"x": 1.5}

    score = indexer.bm25_score("x", "t.md", doc_stats_zero, idf_test)
    assert score > 0, "bm25_avg_dl_zero_positive"


def test_bm25_avg_dl_none_no_crash():
    """avg_dl=None (from corrupt index) shouldn't crash."""
    doc_stats_none = {"avg_dl": None, "docs": {"t.md": {"tf": {"x": 3}, "dl": 10}}}
    idf_test = {"x": 1.5}
    # Should not raise
    indexer.bm25_score("x", "t.md", doc_stats_none, idf_test)


# ============================================================
# Bug 5: MCP input validation
# ============================================================

def test_mcp_search_blocks_int_query_clean_error():
    """Bug 5: MCP clean error messages - search_blocks with integer query."""
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "search_blocks", "arguments": {"query": 123}}
    })
    assert response["result"].get("isError") is True, "mcp_search_int_is_error"
    error_text = response["result"]["content"][0]["text"]
    assert "non-empty string" in error_text, "mcp_search_int_clean_msg"
    assert "attribute" not in error_text.lower(), "mcp_search_int_no_traceback"


def test_mcp_inject_context_int_query_is_error():
    """inject_context with integer query."""
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "inject_context", "arguments": {"query": 456}}
    })
    assert response["result"].get("isError") is True, "mcp_inject_int_is_error"


def test_mcp_inject_context_bad_max_tokens_falls_back():
    """inject_context with bad max_tokens type - should fallback to default."""
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "inject_context", "arguments": {"query": "test", "max_tokens": "bad"}}
    })
    assert "result" in response, "mcp_inject_bad_tokens_ok"
    assert response["result"].get("isError") is not True, "mcp_inject_bad_tokens_not_error"


def test_mcp_inject_context_negative_max_tokens_falls_back():
    """inject_context with negative max_tokens - should fallback."""
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "inject_context", "arguments": {"query": "test", "max_tokens": -1}}
    })
    assert "result" in response, "mcp_inject_neg_tokens_ok"
