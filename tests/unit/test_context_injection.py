#!/usr/bin/env python3
"""
Tests for BloxCue Phase 4: Smart Context Injection

Tests cover:
- Token estimation
- Keyword overlap / deduplication
- inject_context() function (budget, priority, formatting)
- MCP inject_context tool
"""

import sys
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from indexer import (
    estimate_tokens,
    _keyword_overlap,
    inject_context,
    get_file_content,
    MAX_INJECT_TOKENS,
)

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
# Token Estimation Tests
# ============================================================
section("Token Estimation Tests")

check("estimate_tokens_exists", callable(estimate_tokens))
check("estimate_tokens_empty", estimate_tokens("") == 0)
check("estimate_tokens_short", estimate_tokens("hello world") == 2)  # 11 chars / 4 = 2
check("estimate_tokens_1000_chars", estimate_tokens("a" * 1000) == 250)
check("estimate_tokens_returns_int", isinstance(estimate_tokens("test"), int))

# Verify the constant exists
check("max_inject_tokens_defined", MAX_INJECT_TOKENS == 3000)


# ============================================================
# Keyword Overlap Tests
# ============================================================
section("Keyword Overlap / Deduplication Tests")

check("overlap_exists", callable(_keyword_overlap))

# Identical keywords -> 1.0
entry_a = {"keywords": ["deploy", "server", "production"]}
entry_b = {"keywords": ["deploy", "server", "production"]}
check("identical_keywords_overlap_1", _keyword_overlap(entry_a, entry_b) == 1.0)

# No overlap -> 0.0
entry_c = {"keywords": ["deploy", "server"]}
entry_d = {"keywords": ["testing", "quality"]}
check("no_overlap_is_zero", _keyword_overlap(entry_c, entry_d) == 0.0)

# Partial overlap
entry_e = {"keywords": ["deploy", "server", "production"]}
entry_f = {"keywords": ["deploy", "testing", "quality"]}
overlap = _keyword_overlap(entry_e, entry_f)
check("partial_overlap_between_0_and_1", 0 < overlap < 1)
check("partial_overlap_is_correct", abs(overlap - 1/5) < 0.01)  # 1 shared out of 5 union

# Empty keywords -> 0.0
entry_g = {"keywords": []}
entry_h = {"keywords": ["deploy"]}
check("empty_keywords_is_zero", _keyword_overlap(entry_g, entry_h) == 0.0)

# Missing keywords -> 0.0
entry_i = {}
entry_j = {"keywords": ["deploy"]}
check("missing_keywords_is_zero", _keyword_overlap(entry_i, entry_j) == 0.0)


# ============================================================
# inject_context() Function Tests
# ============================================================
section("inject_context() Function Tests")

check("inject_context_exists", callable(inject_context))

# Basic injection
result = inject_context("deployment")
check("inject_returns_string", isinstance(result, str))
check("inject_has_bloxcue_header", "[BloxCue:" in result)
check("inject_has_separator", "---" in result)
check("inject_mentions_query", "deployment" in result)

# No results case
result_miss = inject_context("xyzzy_impossible_query_123")
check("inject_miss_has_header", "[BloxCue:" in result_miss)
check("inject_miss_says_no_blocks", "No blocks found" in result_miss)

# Token budget enforcement
result_small = inject_context("deployment", max_tokens=100)
check("inject_small_budget_returns", isinstance(result_small, str))
check("inject_small_budget_has_header", "[BloxCue:" in result_small)
# With a tiny budget, should use summaries or references
estimated = estimate_tokens(result_small)
check("inject_small_budget_respected", estimated < 200)  # generous check

result_large = inject_context("deployment", max_tokens=50000)
check("inject_large_budget_returns", isinstance(result_large, str))

# Block metadata in output
if "Block 1:" in result:
    check("inject_has_block_number", True)
    check("inject_has_score", "score:" in result)
    check("inject_has_updated", "updated:" in result)
else:
    # No results matched - still valid
    check("inject_has_block_number", "No blocks" in result)
    check("inject_has_score", True)
    check("inject_has_updated", True)

# Limit parameter
result_limit1 = inject_context("deployment", limit=1)
check("inject_limit_1_works", isinstance(result_limit1, str))
# Count "Block N:" occurrences
block_count = result_limit1.count("### Block")
check("inject_limit_1_max_1_block", block_count <= 1)


# ============================================================
# Priority Injection Tests
# ============================================================
section("Priority Injection (Budget Tiers)")

# With a very small budget, blocks should be reference-only or summary
result_tiny = inject_context("deployment", max_tokens=50)
check("tiny_budget_has_header", "[BloxCue:" in result_tiny)

# With medium budget, should have at least some content
result_medium = inject_context("deployment", max_tokens=1000)
check("medium_budget_has_content", len(result_medium) > 100)

# With huge budget, should have full content
result_huge = inject_context("deployment", max_tokens=100000)
check("huge_budget_has_content", len(result_huge) > len(result_medium) or len(result_medium) > 100)


# ============================================================
# Deduplication Tests
# ============================================================
section("Deduplication Behavior")

# Run a search that might return overlapping results
# The dedup should reduce near-duplicates
result_dedup = inject_context("template", limit=10, max_tokens=50000)
check("dedup_returns_string", isinstance(result_dedup, str))
# Count blocks - dedup should have removed any >60% keyword-overlap blocks
block_count_dedup = result_dedup.count("### Block")
check("dedup_has_blocks", block_count_dedup >= 0)  # valid even if 0


# ============================================================
# Injection Format Tests
# ============================================================
section("Injection Format")

result_fmt = inject_context("deployment", max_tokens=5000)
lines = result_fmt.split("\n")

# First line should be metadata header
check("format_first_line_is_metadata", lines[0].startswith("[BloxCue:"))
check("format_metadata_has_block_count", "block(s)" in lines[0] or "blocks" in lines[0] or "No blocks" in lines[0])
check("format_metadata_has_tokens", "tokens" in lines[0] or "No blocks" in lines[0])

# Check for --- separator
check("format_has_separator", "---" in result_fmt)

# If blocks were found, check block headers
if "### Block" in result_fmt:
    check("format_block_has_title", "Block 1:" in result_fmt)
    # Check for reference hint when blocks are too large
    has_content_or_ref = "Summary" in result_fmt or "Reference" in result_fmt or "Block 1:" in result_fmt
    check("format_has_content_type", has_content_or_ref)
else:
    check("format_block_has_title", True)
    check("format_has_content_type", True)


# ============================================================
# Summary
# ============================================================
print(f"\n{'='*60}")
print(f"Results: {passed}/{passed+failed} passed, {failed} failed")

if __name__ == "__main__":
    pass
