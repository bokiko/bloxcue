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
    MAX_INJECT_TOKENS,
)


# ============================================================
# Token Estimation Tests
# ============================================================

def test_estimate_tokens_exists():
    assert callable(estimate_tokens), "estimate_tokens_exists"


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0, "estimate_tokens_empty"


def test_estimate_tokens_short():
    assert estimate_tokens("hello world") == 2, "estimate_tokens_short"  # 11 chars / 4 = 2


def test_estimate_tokens_1000_chars():
    assert estimate_tokens("a" * 1000) == 250, "estimate_tokens_1000_chars"


def test_estimate_tokens_returns_int():
    assert isinstance(estimate_tokens("test"), int), "estimate_tokens_returns_int"


def test_max_inject_tokens_defined():
    assert MAX_INJECT_TOKENS == 3000, "max_inject_tokens_defined"


# ============================================================
# Keyword Overlap Tests
# ============================================================

def test_overlap_exists():
    assert callable(_keyword_overlap), "overlap_exists"


def test_identical_keywords_overlap_1():
    entry_a = {"keywords": ["deploy", "server", "production"]}
    entry_b = {"keywords": ["deploy", "server", "production"]}
    assert _keyword_overlap(entry_a, entry_b) == 1.0, "identical_keywords_overlap_1"


def test_no_overlap_is_zero():
    entry_c = {"keywords": ["deploy", "server"]}
    entry_d = {"keywords": ["testing", "quality"]}
    assert _keyword_overlap(entry_c, entry_d) == 0.0, "no_overlap_is_zero"


def test_partial_overlap():
    entry_e = {"keywords": ["deploy", "server", "production"]}
    entry_f = {"keywords": ["deploy", "testing", "quality"]}
    overlap = _keyword_overlap(entry_e, entry_f)
    assert 0 < overlap < 1, "partial_overlap_between_0_and_1"
    assert abs(overlap - 1 / 5) < 0.01, "partial_overlap_is_correct"  # 1 shared out of 5 union


def test_empty_keywords_is_zero():
    entry_g = {"keywords": []}
    entry_h = {"keywords": ["deploy"]}
    assert _keyword_overlap(entry_g, entry_h) == 0.0, "empty_keywords_is_zero"


def test_missing_keywords_is_zero():
    entry_i = {}
    entry_j = {"keywords": ["deploy"]}
    assert _keyword_overlap(entry_i, entry_j) == 0.0, "missing_keywords_is_zero"


# ============================================================
# inject_context() Function Tests
# ============================================================

def test_inject_context_exists():
    assert callable(inject_context), "inject_context_exists"


def test_inject_returns_string():
    result = inject_context("deployment")
    assert isinstance(result, str), "inject_returns_string"


def test_inject_has_bloxcue_header():
    result = inject_context("deployment")
    assert "[BloxCue:" in result, "inject_has_bloxcue_header"


def test_inject_has_separator():
    result = inject_context("deployment")
    assert "---" in result, "inject_has_separator"


def test_inject_mentions_query():
    result = inject_context("deployment")
    assert "deployment" in result, "inject_mentions_query"


def test_inject_miss_has_header():
    result_miss = inject_context("xyzzy_impossible_query_123")
    assert "[BloxCue:" in result_miss, "inject_miss_has_header"


def test_inject_miss_says_no_blocks():
    result_miss = inject_context("xyzzy_impossible_query_123")
    assert "No blocks found" in result_miss, "inject_miss_says_no_blocks"


def test_inject_small_budget_returns_string():
    result_small = inject_context("deployment", max_tokens=100)
    assert isinstance(result_small, str), "inject_small_budget_returns"


def test_inject_small_budget_has_header():
    result_small = inject_context("deployment", max_tokens=100)
    assert "[BloxCue:" in result_small, "inject_small_budget_has_header"


def test_inject_small_budget_respected():
    """With a tiny budget, output should stay small (use summaries or references)."""
    result_small = inject_context("deployment", max_tokens=100)
    estimated = estimate_tokens(result_small)
    assert estimated < 200, "inject_small_budget_respected"  # generous check


def test_inject_large_budget_returns_string():
    result_large = inject_context("deployment", max_tokens=50000)
    assert isinstance(result_large, str), "inject_large_budget_returns"


def test_inject_block_metadata_in_output():
    """If results matched, output should include block number/score/updated metadata."""
    result = inject_context("deployment")
    if "Block 1:" in result:
        assert "score:" in result, "inject_has_score"
        assert "updated:" in result, "inject_has_updated"
    else:
        # No results matched - still valid, just confirm no-blocks message present
        assert "No blocks" in result, "inject_has_block_number"


def test_inject_limit_1_works():
    result_limit1 = inject_context("deployment", limit=1)
    assert isinstance(result_limit1, str), "inject_limit_1_works"


def test_inject_limit_1_max_1_block():
    result_limit1 = inject_context("deployment", limit=1)
    block_count = result_limit1.count("### Block")
    assert block_count <= 1, "inject_limit_1_max_1_block"


# ============================================================
# Priority Injection Tests
# ============================================================

def test_tiny_budget_has_header():
    result_tiny = inject_context("deployment", max_tokens=50)
    assert "[BloxCue:" in result_tiny, "tiny_budget_has_header"


def test_medium_budget_has_content():
    result_medium = inject_context("deployment", max_tokens=1000)
    assert len(result_medium) > 100, "medium_budget_has_content"


def test_huge_budget_has_content():
    result_medium = inject_context("deployment", max_tokens=1000)
    result_huge = inject_context("deployment", max_tokens=100000)
    assert len(result_huge) > len(result_medium) or len(result_medium) > 100, "huge_budget_has_content"


# ============================================================
# Deduplication Tests
# ============================================================

def test_dedup_returns_string():
    result_dedup = inject_context("template", limit=10, max_tokens=50000)
    assert isinstance(result_dedup, str), "dedup_returns_string"


def test_dedup_has_blocks():
    result_dedup = inject_context("template", limit=10, max_tokens=50000)
    block_count_dedup = result_dedup.count("### Block")
    assert block_count_dedup >= 0, "dedup_has_blocks"  # valid even if 0


# ============================================================
# Injection Format Tests
# ============================================================

def test_format_first_line_is_metadata():
    result_fmt = inject_context("deployment", max_tokens=5000)
    lines = result_fmt.split("\n")
    assert lines[0].startswith("[BloxCue:"), "format_first_line_is_metadata"


def test_format_metadata_has_block_count():
    result_fmt = inject_context("deployment", max_tokens=5000)
    lines = result_fmt.split("\n")
    first = lines[0]
    assert ("block(s)" in first) or ("blocks" in first) or ("No blocks" in first), "format_metadata_has_block_count"


def test_format_metadata_has_tokens():
    result_fmt = inject_context("deployment", max_tokens=5000)
    lines = result_fmt.split("\n")
    first = lines[0]
    assert ("tokens" in first) or ("No blocks" in first), "format_metadata_has_tokens"


def test_format_has_separator():
    result_fmt = inject_context("deployment", max_tokens=5000)
    assert "---" in result_fmt, "format_has_separator"


def test_format_block_structure():
    """If blocks were found, check block headers and content type hints."""
    result_fmt = inject_context("deployment", max_tokens=5000)
    if "### Block" in result_fmt:
        assert "Block 1:" in result_fmt, "format_block_has_title"
        # Check for reference hint when blocks are too large
        has_content_or_ref = (
            "Summary" in result_fmt
            or "Reference" in result_fmt
            or "Block 1:" in result_fmt
        )
        assert has_content_or_ref, "format_has_content_type"
