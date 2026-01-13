#!/usr/bin/env python3
"""
Tests for BloxCue Indexer Tier 1 Improvements

Tests cover:
- Phase 1: Porter Stemmer
- Phase 2: IDF Weighting
- Phase 3: Bigram Indexing
- Phase 4: Query Intent Detection
"""

import sys
import math
from pathlib import Path

# Add scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from indexer import (
    normalize_word,
    simple_stem,
)


class TestResult:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def success(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name, error):
        self.failed += 1
        self.errors.append((name, error))
        print(f"  [FAIL] {name}: {error}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} passed, {self.failed} failed")
        if self.errors:
            print("\nFailures:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        return self.failed == 0


def run_test(result, name, test_func):
    """Run a single test and record result."""
    try:
        test_func()
        result.success(name)
    except AssertionError as e:
        result.fail(name, str(e) or "Assertion failed")
    except ImportError as e:
        result.fail(name, f"Import error: {e}")
    except Exception as e:
        result.fail(name, f"Error: {type(e).__name__}: {e}")


# =============================================================================
# Phase 1: Porter Stemmer Tests
# =============================================================================

def test_porter_stem_exists():
    """porter_stem function should exist."""
    from indexer import porter_stem
    assert callable(porter_stem), "porter_stem should be callable"


def test_porter_stem_running():
    """'running' should stem to 'run'."""
    from indexer import porter_stem
    result = porter_stem("running")
    assert result == "run", f"Expected 'run', got '{result}'"


def test_porter_stem_cats():
    """'cats' should stem to 'cat'."""
    from indexer import porter_stem
    result = porter_stem("cats")
    assert result == "cat", f"Expected 'cat', got '{result}'"


def test_porter_stem_agreed():
    """'agreed' should stem to 'agre'."""
    from indexer import porter_stem
    result = porter_stem("agreed")
    assert result == "agre", f"Expected 'agre', got '{result}'"


def test_porter_stem_relational():
    """'relational' should stem to 'relat'."""
    from indexer import porter_stem
    result = porter_stem("relational")
    assert result == "relat", f"Expected 'relat', got '{result}'"


def test_porter_stem_computational():
    """'computational' should stem to 'comput'."""
    from indexer import porter_stem
    result = porter_stem("computational")
    assert result == "comput", f"Expected 'comput', got '{result}'"


def test_porter_stem_caresses():
    """'caresses' should stem to 'caress'."""
    from indexer import porter_stem
    result = porter_stem("caresses")
    assert result == "caress", f"Expected 'caress', got '{result}'"


def test_porter_stem_ponies():
    """'ponies' should stem to 'poni'."""
    from indexer import porter_stem
    result = porter_stem("ponies")
    assert result == "poni", f"Expected 'poni', got '{result}'"


def test_porter_stem_ties():
    """'ties' should stem to 'ti'."""
    from indexer import porter_stem
    result = porter_stem("ties")
    assert result == "ti", f"Expected 'ti', got '{result}'"


def test_porter_stem_hopping():
    """'hopping' should stem to 'hop'."""
    from indexer import porter_stem
    result = porter_stem("hopping")
    assert result == "hop", f"Expected 'hop', got '{result}'"


def test_porter_stem_disabled():
    """'disabled' should stem to 'disabl'."""
    from indexer import porter_stem
    result = porter_stem("disabled")
    assert result == "disabl", f"Expected 'disabl', got '{result}'"


def test_simple_stem_uses_porter():
    """simple_stem should now use porter_stem internally."""
    from indexer import porter_stem
    result = simple_stem("running")
    expected = porter_stem(normalize_word("running"))
    assert result == expected, f"simple_stem should delegate to porter_stem"


# =============================================================================
# Phase 2: IDF Weighting Tests
# =============================================================================

def test_calculate_idf_exists():
    """calculate_idf function should exist."""
    from indexer import calculate_idf
    assert callable(calculate_idf), "calculate_idf should be callable"


def test_calculate_idf_basic():
    """IDF should be calculated correctly for terms."""
    from indexer import calculate_idf

    mock_index = {
        "files": [
            {"title": "Common Term", "tags": ["common"], "keywords": ["common"]},
            {"title": "Common Again", "tags": ["common"], "keywords": ["test"]},
            {"title": "Rare Special", "tags": ["rare"], "keywords": ["special"]},
        ]
    }

    idf = calculate_idf(mock_index)
    assert isinstance(idf, dict), "IDF should be a dict"
    assert len(idf) > 0, "IDF should have entries"


def test_idf_rare_vs_common():
    """Rare terms should have higher IDF than common terms."""
    from indexer import calculate_idf, porter_stem

    mock_index = {
        "files": [
            {"title": "Common Doc One", "tags": ["common"], "keywords": ["shared"]},
            {"title": "Common Doc Two", "tags": ["common"], "keywords": ["shared"]},
            {"title": "Common Doc Three", "tags": ["common"], "keywords": ["shared"]},
            {"title": "Rare Unique Doc", "tags": ["rare"], "keywords": ["unique"]},
        ]
    }

    idf = calculate_idf(mock_index)

    common_stem = porter_stem("common")
    rare_stem = porter_stem("rare")

    assert idf.get(rare_stem, 0) > idf.get(common_stem, 0), \
        f"Rare term IDF ({idf.get(rare_stem, 0)}) should be > common term IDF ({idf.get(common_stem, 0)})"


# =============================================================================
# Phase 3: Bigram Indexing Tests
# =============================================================================

def test_extract_bigrams_exists():
    """extract_bigrams function should exist."""
    from indexer import extract_bigrams
    assert callable(extract_bigrams), "extract_bigrams should be callable"


def test_extract_bigrams_from_title():
    """Bigrams should be extracted from title."""
    from indexer import extract_bigrams

    content = "Some body content"
    frontmatter = {"title": "Error Handling Guide"}

    bigrams = extract_bigrams(content, frontmatter)
    assert isinstance(bigrams, list), "Bigrams should be a list"
    # Should have error-handling or error-handl depending on stemming
    has_error_handling = any("error" in b and "handl" in b for b in bigrams)
    assert has_error_handling, f"Should extract 'error-handling' bigram, got: {bigrams}"


def test_extract_bigrams_from_headings():
    """Bigrams should be extracted from headings."""
    from indexer import extract_bigrams

    content = """# API Reference
## Getting Started
Some content here.
"""
    frontmatter = {"title": "Documentation"}

    bigrams = extract_bigrams(content, frontmatter)
    assert isinstance(bigrams, list), "Bigrams should be a list"


def test_bigrams_filter_stopwords():
    """Stopwords should be filtered before bigram extraction."""
    from indexer import extract_bigrams

    content = "# The Quick Guide"
    frontmatter = {"title": "A Simple Test"}

    bigrams = extract_bigrams(content, frontmatter)
    # "the" and "a" are stopwords, should not appear as bigram starts
    bad_bigrams = [b for b in bigrams if b.startswith("the-") or b.startswith("a-")]
    assert len(bad_bigrams) == 0, f"Stopwords should be filtered: {bad_bigrams}"


# =============================================================================
# Phase 4: Query Intent Detection Tests
# =============================================================================

def test_detect_query_intent_exists():
    """detect_query_intent function should exist."""
    from indexer import detect_query_intent
    assert callable(detect_query_intent), "detect_query_intent should be callable"


def test_detect_howto_intent():
    """'how to' queries should detect howto intent."""
    from indexer import detect_query_intent

    intent, adjustments = detect_query_intent("how to setup claude")
    assert intent == "howto", f"Expected 'howto' intent, got '{intent}'"
    assert isinstance(adjustments, dict), "Adjustments should be a dict"


def test_detect_troubleshoot_intent():
    """'error' queries should detect troubleshoot intent."""
    from indexer import detect_query_intent

    intent, adjustments = detect_query_intent("error not working")
    assert intent == "troubleshoot", f"Expected 'troubleshoot' intent, got '{intent}'"


def test_detect_concept_intent():
    """'what is' queries should detect concept intent."""
    from indexer import detect_query_intent

    intent, adjustments = detect_query_intent("what is docker")
    assert intent == "concept", f"Expected 'concept' intent, got '{intent}'"


def test_detect_reference_intent():
    """'api' queries should detect reference intent."""
    from indexer import detect_query_intent

    intent, adjustments = detect_query_intent("api documentation")
    assert intent == "reference", f"Expected 'reference' intent, got '{intent}'"


def test_detect_general_intent():
    """Queries without clear intent should return 'general'."""
    from indexer import detect_query_intent

    intent, adjustments = detect_query_intent("random stuff here")
    assert intent == "general", f"Expected 'general' intent, got '{intent}'"
    assert adjustments == {}, f"General intent should have no adjustments, got {adjustments}"


def test_intent_adjustments_structure():
    """Intent adjustments should be a dict of field -> multiplier."""
    from indexer import detect_query_intent

    intent, adjustments = detect_query_intent("how to install")

    if adjustments:
        for key, value in adjustments.items():
            assert isinstance(key, str), f"Adjustment key should be string: {key}"
            assert isinstance(value, (int, float)), f"Adjustment value should be number: {value}"


# =============================================================================
# Integration Tests
# =============================================================================

def test_search_with_improvements():
    """Search should use all new features when available."""
    from indexer import search

    results = search("test query")
    assert isinstance(results, list), "Search should return a list"


def test_intent_patterns_exists():
    """INTENT_PATTERNS dictionary should exist in module."""
    from indexer import INTENT_PATTERNS
    assert isinstance(INTENT_PATTERNS, dict), "INTENT_PATTERNS should be a dict"
    assert "howto" in INTENT_PATTERNS, "INTENT_PATTERNS should have 'howto'"
    assert "troubleshoot" in INTENT_PATTERNS, "INTENT_PATTERNS should have 'troubleshoot'"


# =============================================================================
# Main Test Runner
# =============================================================================

def main():
    result = TestResult()

    print("\n" + "="*60)
    print("BloxCue Indexer Tier 1 Improvements - Test Suite")
    print("="*60)

    # Phase 1: Porter Stemmer
    print("\nPhase 1: Porter Stemmer Tests")
    print("-" * 40)
    run_test(result, "porter_stem_exists", test_porter_stem_exists)
    run_test(result, "porter_stem_running", test_porter_stem_running)
    run_test(result, "porter_stem_cats", test_porter_stem_cats)
    run_test(result, "porter_stem_agreed", test_porter_stem_agreed)
    run_test(result, "porter_stem_relational", test_porter_stem_relational)
    run_test(result, "porter_stem_computational", test_porter_stem_computational)
    run_test(result, "porter_stem_caresses", test_porter_stem_caresses)
    run_test(result, "porter_stem_ponies", test_porter_stem_ponies)
    run_test(result, "porter_stem_ties", test_porter_stem_ties)
    run_test(result, "porter_stem_hopping", test_porter_stem_hopping)
    run_test(result, "porter_stem_disabled", test_porter_stem_disabled)
    run_test(result, "simple_stem_uses_porter", test_simple_stem_uses_porter)

    # Phase 2: IDF Weighting
    print("\nPhase 2: IDF Weighting Tests")
    print("-" * 40)
    run_test(result, "calculate_idf_exists", test_calculate_idf_exists)
    run_test(result, "calculate_idf_basic", test_calculate_idf_basic)
    run_test(result, "idf_rare_vs_common", test_idf_rare_vs_common)

    # Phase 3: Bigram Indexing
    print("\nPhase 3: Bigram Indexing Tests")
    print("-" * 40)
    run_test(result, "extract_bigrams_exists", test_extract_bigrams_exists)
    run_test(result, "extract_bigrams_from_title", test_extract_bigrams_from_title)
    run_test(result, "extract_bigrams_from_headings", test_extract_bigrams_from_headings)
    run_test(result, "bigrams_filter_stopwords", test_bigrams_filter_stopwords)

    # Phase 4: Query Intent Detection
    print("\nPhase 4: Query Intent Detection Tests")
    print("-" * 40)
    run_test(result, "detect_query_intent_exists", test_detect_query_intent_exists)
    run_test(result, "detect_howto_intent", test_detect_howto_intent)
    run_test(result, "detect_troubleshoot_intent", test_detect_troubleshoot_intent)
    run_test(result, "detect_concept_intent", test_detect_concept_intent)
    run_test(result, "detect_reference_intent", test_detect_reference_intent)
    run_test(result, "detect_general_intent", test_detect_general_intent)
    run_test(result, "intent_adjustments_structure", test_intent_adjustments_structure)

    # Integration Tests
    print("\nIntegration Tests")
    print("-" * 40)
    run_test(result, "search_with_improvements", test_search_with_improvements)
    run_test(result, "intent_patterns_exists", test_intent_patterns_exists)

    # Summary
    all_passed = result.summary()
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
