#!/usr/bin/env python3
"""
Tests for BloxCue Phase 3: Block Health System

Tests cover:
- Usage logging (log_usage, load_usage_log)
- Health report generation
- Gap detection (missed queries)
- CLI --health flag
- MCP server block_health integration
"""

import sys
import json
from pathlib import Path

# Add project dirs to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import indexer
import mcp_server


# ============================================================
# Usage Logging Tests
# ============================================================

def test_log_usage_exists():
    assert callable(indexer.log_usage), "log_usage_exists"


def test_load_usage_log_exists():
    assert callable(indexer.load_usage_log), "load_usage_log_exists"


def test_usage_file_defined():
    assert hasattr(indexer, "USAGE_FILE"), "usage_file_defined"


def test_usage_file_is_jsonl():
    # v3.0.1: usage log moved from <SCRIPT_DIR>/.usage.jsonl to
    # <MEMORY_DIR>/.bloxcue/usage.jsonl. The .bloxcue parent dir is
    # already hidden so the file itself no longer needs a dotfile prefix.
    assert str(indexer.USAGE_FILE).endswith("usage.jsonl"), "usage_file_is_jsonl"


def test_log_usage_writes_records():
    """Test log_usage writes records and load_usage_log reads them back."""
    original_usage_file = indexer.USAGE_FILE
    temp_usage = SCRIPTS_DIR / ".test_usage.jsonl"
    indexer.USAGE_FILE = temp_usage

    try:
        if temp_usage.exists():
            temp_usage.unlink()

        # Log a usage record
        mock_results = [
            {"entry": {"path": "test/doc.md", "title": "Test Doc"}, "score": 5.0},
            {"entry": {"path": "test/other.md", "title": "Other"}, "score": 2.0},
        ]
        indexer.log_usage("test query", mock_results)

        assert temp_usage.exists(), "log_usage_creates_file"

        # Read and verify the record
        content = temp_usage.read_text().strip()
        record = json.loads(content)
        assert "timestamp" in record, "record_has_timestamp"
        assert record["query"] == "test query", "record_has_query"
        assert record["results"] == ["test/doc.md", "test/other.md"], "record_has_results"
        assert record["scores"] == [5.0, 2.0], "record_has_scores"
        assert record["hit"] is True, "record_has_hit_true"

        # Log a miss (no results)
        indexer.log_usage("missing query", [])
        lines = temp_usage.read_text().strip().split("\n")
        miss_record = json.loads(lines[1])
        assert miss_record["hit"] is False, "miss_record_hit_false"
        assert miss_record["results"] == [], "miss_record_empty_results"

        # Test load_usage_log
        records = indexer.load_usage_log()
        assert isinstance(records, list), "load_returns_list"
        assert len(records) == 2, "load_returns_2_records"
        assert records[0]["hit"] is True, "load_first_is_hit"
        assert records[1]["hit"] is False, "load_second_is_miss"

    finally:
        indexer.USAGE_FILE = original_usage_file
        if temp_usage.exists():
            temp_usage.unlink()


def test_load_usage_log_missing_file_returns_empty():
    """Test load_usage_log with no file."""
    original_usage_file = indexer.USAGE_FILE
    indexer.USAGE_FILE = SCRIPTS_DIR / ".nonexistent_usage.jsonl"
    try:
        records = indexer.load_usage_log()
        assert records == [], "load_missing_file_returns_empty"
    finally:
        indexer.USAGE_FILE = original_usage_file


# ============================================================
# Health Report Tests
# ============================================================

def test_generate_health_report_exists():
    assert callable(indexer.generate_health_report), "generate_health_report_exists"


def test_health_report_basic_structure():
    """Health report should be a string with expected sections."""
    report = indexer.generate_health_report()
    assert isinstance(report, str), "report_is_string"
    assert "Block Health Report" in report, "report_has_title"
    assert "Total blocks:" in report, "report_has_total"
    assert "Fresh" in report, "report_has_fresh"
    assert "Aging" in report, "report_has_aging"
    assert "Stale" in report, "report_has_stale"
    assert "Distinctive Terms" in report, "report_has_idf_section"


# ============================================================
# Search Logs Usage Automatically
# ============================================================

def test_search_creates_usage_log():
    """Search should auto-log usage."""
    original_usage_file = indexer.USAGE_FILE
    temp_usage = SCRIPTS_DIR / ".test_search_usage.jsonl"
    indexer.USAGE_FILE = temp_usage

    try:
        if temp_usage.exists():
            temp_usage.unlink()

        # Perform a search - should auto-log
        indexer.search("deployment")
        assert temp_usage.exists(), "search_creates_usage_log"

        records = indexer.load_usage_log()
        assert len(records) == 1, "search_logged_1_record"
        assert records[0]["query"] == "deployment", "search_logged_query"
        assert records[0]["hit"] is True, "search_logged_hit"

        # Search for something that won't match
        indexer.search("xyzzy_no_match_123")
        records2 = indexer.load_usage_log()
        assert len(records2) == 2, "miss_search_logged"
        assert records2[1]["hit"] is False, "miss_search_hit_false"

    finally:
        indexer.USAGE_FILE = original_usage_file
        if temp_usage.exists():
            temp_usage.unlink()


# ============================================================
# Gap Detection Tests
# ============================================================

def test_gap_detection_in_health_report():
    """Health report should surface gaps based on missed queries."""
    original_usage_file = indexer.USAGE_FILE
    temp_usage = SCRIPTS_DIR / ".test_gaps_usage.jsonl"
    indexer.USAGE_FILE = temp_usage

    try:
        if temp_usage.exists():
            temp_usage.unlink()

        # Log several missed queries
        for _ in range(3):
            indexer.log_usage("kubernetes setup", [])
        for _ in range(2):
            indexer.log_usage("docker compose", [])
        indexer.log_usage("deployment", [{"entry": {"path": "x.md"}, "score": 1.0}])

        report = indexer.generate_health_report()
        assert "Knowledge Gaps" in report, "gap_report_has_gaps_section"
        assert "kubernetes" in report.lower(), "gap_report_shows_kubernetes"
        assert "docker" in report.lower(), "gap_report_shows_docker"
        assert "Hit rate" in report, "gap_report_has_hit_rate"

        # Verify suggestions mention creating blocks for repeated gaps
        assert "Suggestions" in report, "gap_suggestions_present"
        assert "kubernetes" in report.lower(), "gap_suggests_kubernetes"

    finally:
        indexer.USAGE_FILE = original_usage_file
        if temp_usage.exists():
            temp_usage.unlink()


# ============================================================
# MCP Server Integration Tests
# ============================================================

def test_mcp_server_block_health_integration():
    """MCP server should expose block_health tool."""
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "block_health", "arguments": {}}
    })
    assert "result" in response, "mcp_health_succeeds"
    text = response["result"]["content"][0]["text"]
    assert "Block Health Report" in text, "mcp_health_has_report"
    assert "Total blocks:" in text, "mcp_health_has_totals"
