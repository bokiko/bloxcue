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
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Add project dirs to path
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
# Usage Logging Tests
# ============================================================
section("Usage Logging Tests")

# Test log_usage function exists and is callable
check("log_usage_exists", callable(indexer.log_usage))
check("load_usage_log_exists", callable(indexer.load_usage_log))

# Test USAGE_FILE constant
check("usage_file_defined", hasattr(indexer, "USAGE_FILE"))
check("usage_file_is_jsonl", str(indexer.USAGE_FILE).endswith(".usage.jsonl"))

# Test log_usage writes a record
# Save original and use temp file
original_usage_file = indexer.USAGE_FILE
temp_usage = SCRIPTS_DIR / ".test_usage.jsonl"
indexer.USAGE_FILE = temp_usage

try:
    # Clean up any previous test file
    if temp_usage.exists():
        temp_usage.unlink()

    # Log a usage record
    mock_results = [
        {"entry": {"path": "test/doc.md", "title": "Test Doc"}, "score": 5.0},
        {"entry": {"path": "test/other.md", "title": "Other"}, "score": 2.0},
    ]
    indexer.log_usage("test query", mock_results)

    check("log_usage_creates_file", temp_usage.exists())

    # Read and verify the record
    content = temp_usage.read_text().strip()
    record = json.loads(content)
    check("record_has_timestamp", "timestamp" in record)
    check("record_has_query", record["query"] == "test query")
    check("record_has_results", record["results"] == ["test/doc.md", "test/other.md"])
    check("record_has_scores", record["scores"] == [5.0, 2.0])
    check("record_has_hit_true", record["hit"] is True)

    # Log a miss (no results)
    indexer.log_usage("missing query", [])
    lines = temp_usage.read_text().strip().split("\n")
    miss_record = json.loads(lines[1])
    check("miss_record_hit_false", miss_record["hit"] is False)
    check("miss_record_empty_results", miss_record["results"] == [])

    # Test load_usage_log
    records = indexer.load_usage_log()
    check("load_returns_list", isinstance(records, list))
    check("load_returns_2_records", len(records) == 2)
    check("load_first_is_hit", records[0]["hit"] is True)
    check("load_second_is_miss", records[1]["hit"] is False)

finally:
    # Restore original and clean up
    indexer.USAGE_FILE = original_usage_file
    if temp_usage.exists():
        temp_usage.unlink()


# Test load_usage_log with no file
original_usage_file2 = indexer.USAGE_FILE
indexer.USAGE_FILE = SCRIPTS_DIR / ".nonexistent_usage.jsonl"
try:
    records = indexer.load_usage_log()
    check("load_missing_file_returns_empty", records == [])
finally:
    indexer.USAGE_FILE = original_usage_file2


# ============================================================
# Health Report Tests
# ============================================================
section("Health Report Tests")

check("generate_health_report_exists", callable(indexer.generate_health_report))

report = indexer.generate_health_report()
check("report_is_string", isinstance(report, str))
check("report_has_title", "Block Health Report" in report)
check("report_has_total", "Total blocks:" in report)
check("report_has_fresh", "Fresh" in report)
check("report_has_aging", "Aging" in report)
check("report_has_stale", "Stale" in report)

# Report should contain IDF stats
check("report_has_idf_section", "Distinctive Terms" in report)


# ============================================================
# Search Logs Usage Automatically
# ============================================================
section("Search Usage Integration")

# Save original usage file and use temp
original_usage_file3 = indexer.USAGE_FILE
temp_usage3 = SCRIPTS_DIR / ".test_search_usage.jsonl"
indexer.USAGE_FILE = temp_usage3

try:
    if temp_usage3.exists():
        temp_usage3.unlink()

    # Perform a search - should auto-log
    results = indexer.search("deployment")
    check("search_creates_usage_log", temp_usage3.exists())

    records = indexer.load_usage_log()
    check("search_logged_1_record", len(records) == 1)
    check("search_logged_query", records[0]["query"] == "deployment")
    check("search_logged_hit", records[0]["hit"] is True)

    # Search for something that won't match
    results2 = indexer.search("xyzzy_no_match_123")
    records2 = indexer.load_usage_log()
    check("miss_search_logged", len(records2) == 2)
    check("miss_search_hit_false", records2[1]["hit"] is False)

finally:
    indexer.USAGE_FILE = original_usage_file3
    if temp_usage3.exists():
        temp_usage3.unlink()


# ============================================================
# Gap Detection Tests
# ============================================================
section("Gap Detection in Health Report")

# Use temp usage file with known gaps
original_usage_file4 = indexer.USAGE_FILE
temp_usage4 = SCRIPTS_DIR / ".test_gaps_usage.jsonl"
indexer.USAGE_FILE = temp_usage4

try:
    if temp_usage4.exists():
        temp_usage4.unlink()

    # Log several missed queries
    for _ in range(3):
        indexer.log_usage("kubernetes setup", [])
    for _ in range(2):
        indexer.log_usage("docker compose", [])
    indexer.log_usage("deployment", [{"entry": {"path": "x.md"}, "score": 1.0}])

    report = indexer.generate_health_report()
    check("gap_report_has_gaps_section", "Knowledge Gaps" in report)
    check("gap_report_shows_kubernetes", "kubernetes" in report.lower())
    check("gap_report_shows_docker", "docker" in report.lower())
    check("gap_report_has_hit_rate", "Hit rate" in report)

    # Verify suggestions mention creating blocks for repeated gaps
    check("gap_suggestions_present", "Suggestions" in report)
    check("gap_suggests_kubernetes", "kubernetes" in report.lower())

finally:
    indexer.USAGE_FILE = original_usage_file4
    if temp_usage4.exists():
        temp_usage4.unlink()


# ============================================================
# MCP Server Integration Tests
# ============================================================
section("MCP Server block_health Integration")

response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {"name": "block_health", "arguments": {}}
})
check("mcp_health_succeeds", "result" in response)
text = response["result"]["content"][0]["text"]
check("mcp_health_has_report", "Block Health Report" in text)
check("mcp_health_has_totals", "Total blocks:" in text)


# ============================================================
# Summary
# ============================================================
print(f"\n{'='*60}")
print(f"Results: {passed}/{passed+failed} passed, {failed} failed")

if __name__ == "__main__":
    pass
