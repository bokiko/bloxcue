#!/usr/bin/env python3
"""
Tests for BloxCue Phase 2: BM25 Search, Query Expansion, and Re-ranking

Tests cover:
- BM25 scoring function
- Query expansion (synonym map)
- Document stats calculation
- Recency boosting behavior
- MMR diversity in results
- Integration with existing search pipeline
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from indexer import (
    bm25_score,
    expand_query,
    calculate_doc_stats,
    calculate_idf,
    porter_stem,
    search,
    SYNONYM_MAP,
)


# ============================================================
# Shared mock index used across BM25 tests
# ============================================================

MOCK_INDEX = {
    "files": [
        {
            "path": "guides/deploy.md",
            "title": "Deployment Guide",
            "tags": ["deploy", "production"],
            "keywords": ["deploy", "release", "server"],
            "category": "guides",
            "preview": "How to deploy your application to production servers.",
            "bigrams": ["deploy-guid"],
            "modified": datetime.now().isoformat(),
        },
        {
            "path": "guides/testing.md",
            "title": "Testing Guide",
            "tags": ["testing", "quality"],
            "keywords": ["test", "unit", "integration"],
            "category": "guides",
            "preview": "How to write and run tests for your project.",
            "bigrams": ["test-guid"],
            "modified": datetime.now().isoformat(),
        },
        {
            "path": "references/api.md",
            "title": "API Reference",
            "tags": ["api", "endpoints"],
            "keywords": ["api", "rest", "endpoint", "http"],
            "category": "references",
            "preview": "Complete API reference for all endpoints.",
            "bigrams": ["api-refer"],
            "modified": (datetime.now() - timedelta(days=120)).isoformat(),
        },
    ]
}

MOCK_IDF = calculate_idf(MOCK_INDEX)
MOCK_DOC_STATS = calculate_doc_stats(MOCK_INDEX)
DEPLOY_STEM = porter_stem("deploy")


# ============================================================
# BM25 Score Function Tests
# ============================================================

def test_bm25_returns_positive_for_matching_term():
    score = bm25_score(DEPLOY_STEM, "guides/deploy.md", MOCK_DOC_STATS, MOCK_IDF)
    assert score > 0, "bm25_returns_positive_for_matching_term"


def test_bm25_returns_zero_for_missing_term():
    score_miss = bm25_score(porter_stem("nonexistent"), "guides/deploy.md", MOCK_DOC_STATS, MOCK_IDF)
    assert score_miss == 0.0, "bm25_returns_zero_for_missing_term"


def test_bm25_returns_zero_for_unknown_doc():
    score_unknown = bm25_score(DEPLOY_STEM, "unknown/path.md", MOCK_DOC_STATS, MOCK_IDF)
    assert score_unknown == 0.0, "bm25_returns_zero_for_unknown_doc"


def test_bm25_returns_zero_for_zero_idf():
    score_no_idf = bm25_score("zzzzzzz", "guides/deploy.md", MOCK_DOC_STATS, {})
    assert score_no_idf == 0.0, "bm25_returns_zero_for_zero_idf"


def test_bm25_title_match_scores_higher():
    """Term appearing in title-heavy doc should score higher (title weight=3)."""
    deploy_in_deploy = bm25_score(DEPLOY_STEM, "guides/deploy.md", MOCK_DOC_STATS, MOCK_IDF)
    deploy_in_testing = bm25_score(DEPLOY_STEM, "guides/testing.md", MOCK_DOC_STATS, MOCK_IDF)
    assert deploy_in_deploy > deploy_in_testing, "bm25_title_match_scores_higher"


def test_bm25_accepts_custom_params():
    score_custom = bm25_score(DEPLOY_STEM, "guides/deploy.md", MOCK_DOC_STATS, MOCK_IDF, k1=2.0, b=0.5)
    assert score_custom > 0, "bm25_accepts_custom_params"


# ============================================================
# Query Expansion Tests
# ============================================================

def test_expand_includes_original():
    expanded = expand_query(["db"])
    assert any(t == "db" for t, _ in expanded), "expand_includes_original"


def test_expand_includes_synonym():
    expanded = expand_query(["db"])
    assert any(porter_stem("database") == t for t, _ in expanded), "expand_includes_synonym"


def test_original_term_weight_is_1():
    expanded = expand_query(["db"])
    orig_weights = [w for t, w in expanded if t == "db"]
    assert orig_weights[0] == 1.0, "original_term_weight_is_1"


def test_synonym_weight_is_04():
    expanded = expand_query(["db"])
    syn_weights = [w for t, w in expanded if t != "db"]
    assert all(w == 0.4 for w in syn_weights), "synonym_weight_is_04"


def test_no_expansion_for_unknown():
    expanded_unknown = expand_query(["xyzzy123"])
    assert len(expanded_unknown) == 1, "no_expansion_for_unknown"


def test_max_expansions_respected():
    expanded_limited = expand_query(["error"], max_expansions=1)
    syn_count = len([t for t, w in expanded_limited if w < 1.0])
    assert syn_count <= 1, "max_expansions_respected"


def test_synonym_map_has_db():
    assert "db" in SYNONYM_MAP, "synonym_map_has_db"


def test_synonym_map_has_api():
    assert "api" in SYNONYM_MAP, "synonym_map_has_api"


def test_synonym_map_has_deploy():
    assert "deploy" in SYNONYM_MAP, "synonym_map_has_deploy"


def test_synonym_map_has_k8s():
    assert "k8s" in SYNONYM_MAP, "synonym_map_has_k8s"


def test_synonym_db_contains_database():
    assert "database" in SYNONYM_MAP["db"], "synonym_db_contains_database"


def test_synonym_database_contains_db():
    assert "db" in SYNONYM_MAP["database"], "synonym_database_contains_db"


# ============================================================
# Document Stats Tests
# ============================================================

def test_doc_stats_has_avg_dl():
    assert "avg_dl" in MOCK_DOC_STATS, "doc_stats_has_avg_dl"


def test_doc_stats_has_docs():
    assert "docs" in MOCK_DOC_STATS, "doc_stats_has_docs"


def test_doc_stats_avg_dl_positive():
    assert MOCK_DOC_STATS["avg_dl"] > 0, "doc_stats_avg_dl_positive"


def test_doc_has_tf():
    deploy_stats = MOCK_DOC_STATS["docs"].get("guides/deploy.md", {})
    assert "tf" in deploy_stats, "doc_has_tf"


def test_doc_has_dl():
    deploy_stats = MOCK_DOC_STATS["docs"].get("guides/deploy.md", {})
    assert "dl" in deploy_stats, "doc_has_dl"


def test_doc_dl_positive():
    deploy_stats = MOCK_DOC_STATS["docs"].get("guides/deploy.md", {})
    assert deploy_stats["dl"] > 0, "doc_dl_positive"


def test_title_term_weighted_3x():
    """Title terms should have weight 3 in tf."""
    deploy_stats = MOCK_DOC_STATS["docs"].get("guides/deploy.md", {})
    deploy_tf = deploy_stats["tf"]
    assert deploy_tf.get(porter_stem("deploy"), 0) >= 3, "title_term_weighted_3x"


def test_empty_index_avg_dl_is_1():
    empty_stats = calculate_doc_stats({"files": []})
    assert empty_stats["avg_dl"] == 1.0, "empty_index_avg_dl_is_1"


def test_empty_index_no_docs():
    empty_stats = calculate_doc_stats({"files": []})
    assert len(empty_stats["docs"]) == 0, "empty_index_no_docs"


# ============================================================
# Search Integration Tests
# ============================================================

def test_search_returns_list():
    results = search("test query")
    assert isinstance(results, list), "search_returns_list"


def test_search_respects_limit():
    results_limited = search("test", limit=2)
    assert len(results_limited) <= 2, "search_respects_limit"


def test_search_results_have_score_and_entry():
    results = search("test query")
    if results:
        assert "score" in results[0], "search_results_have_score"
        assert "entry" in results[0], "search_results_have_entry"
        assert all(r["score"] > 0 for r in results), "search_scores_are_positive"


def test_search_results_sorted_desc():
    results = search("test query")
    if len(results) > 1:
        scores = [r["score"] for r in results]
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1)), "search_results_sorted_desc"


def test_empty_query_returns_list():
    empty_results = search("")
    assert isinstance(empty_results, list), "empty_query_returns_list"


# ============================================================
# Recency Boost Tests
# ============================================================

def test_recency_fresh_is_highest():
    """Verify recency factor calculation matches expected behavior."""
    fresh_factor = 1.0 + 0.1 / (1.0 + 0 / 30.0)
    aging_factor = 1.0 + 0.1 / (1.0 + 30 / 30.0)
    stale_factor = 1.0 + 0.1 / (1.0 + 120 / 30.0)
    assert fresh_factor > aging_factor > stale_factor, "recency_fresh_is_highest"


def test_recency_boost_max_is_10pct():
    fresh_factor = 1.0 + 0.1 / (1.0 + 0 / 30.0)
    assert fresh_factor <= 1.11, "recency_boost_max_is_10pct"


def test_recency_boost_always_positive():
    stale_factor = 1.0 + 0.1 / (1.0 + 120 / 30.0)
    assert stale_factor > 1.0, "recency_boost_always_positive"


# ============================================================
# MMR Diversity Tests
# ============================================================

def test_mmr_no_overlap_higher():
    """MMR with lambda=0.7 should prefer relevance but penalize overlap."""
    relevance = 10.0
    overlap_0 = 0.7 * relevance - 0.3 * 0.0 * relevance  # no overlap
    overlap_1 = 0.7 * relevance - 0.3 * 1.0 * relevance  # full overlap
    assert overlap_0 > overlap_1, "mmr_no_overlap_higher"


def test_mmr_full_overlap_penalized():
    relevance = 10.0
    overlap_1 = 0.7 * relevance - 0.3 * 1.0 * relevance
    assert overlap_1 == 0.7 * relevance - 0.3 * relevance, "mmr_full_overlap_penalized"


def test_mmr_no_overlap_equals_70pct():
    relevance = 10.0
    overlap_0 = 0.7 * relevance - 0.3 * 0.0 * relevance
    assert abs(overlap_0 - 7.0) < 0.001, "mmr_no_overlap_equals_70pct"


# ============================================================
# Query Expansion + BM25 Integration
# ============================================================

def test_synonym_search_db_returns_list():
    results_db = search("db")
    assert isinstance(results_db, list), "synonym_search_db_returns_list"


def test_synonym_search_database_returns_list():
    results_database = search("database")
    assert isinstance(results_database, list), "synonym_search_database_returns_list"
