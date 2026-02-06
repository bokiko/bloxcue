#!/usr/bin/env python3
"""
Tests for BloxCue PostgreSQL integration.

All tests are mock-based - no running PostgreSQL required.
Tests cover:
  1. pg_provider unit tests (is_available, fetch, conversion)
  2. Integration tests (build_index with mocked PG, search, get_file_content routing)
  3. Fallback tests (PG unavailable, psycopg2 missing)
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

# Add scripts dir to path
SCRIPT_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

# Inject a mock psycopg2 into sys.modules BEFORE importing pg_provider,
# so pg_provider sees HAS_PSYCOPG2=True and has the attribute available for patching.
mock_psycopg2_module = MagicMock()
mock_psycopg2_module.extras = MagicMock()
sys.modules["psycopg2"] = mock_psycopg2_module
sys.modules["psycopg2.extras"] = mock_psycopg2_module.extras

# Force reimport so pg_provider picks up the mock
if "pg_provider" in sys.modules:
    del sys.modules["pg_provider"]

import pg_provider

# Verify the mock worked
assert pg_provider.HAS_PSYCOPG2 is True, "Mock psycopg2 injection failed"


# ============================================================
# pg_provider unit tests
# ============================================================

class TestPgProviderIsAvailable(unittest.TestCase):
    """Test is_available() function."""

    def test_no_psycopg2_returns_false(self):
        """Without psycopg2, is_available returns False."""
        original = pg_provider.HAS_PSYCOPG2
        try:
            pg_provider.HAS_PSYCOPG2 = False
            self.assertFalse(pg_provider.is_available("postgresql://localhost/test"))
        finally:
            pg_provider.HAS_PSYCOPG2 = original

    def test_empty_url_returns_false(self):
        """Empty URL returns False."""
        self.assertFalse(pg_provider.is_available(""))

    def test_successful_connection(self):
        """Successful connection returns True."""
        mock_conn = MagicMock()
        pg_provider.psycopg2.connect.reset_mock()
        pg_provider.psycopg2.connect.return_value = mock_conn
        pg_provider.psycopg2.connect.side_effect = None

        result = pg_provider.is_available("postgresql://localhost/test")

        self.assertTrue(result)
        pg_provider.psycopg2.connect.assert_called_once_with(
            "postgresql://localhost/test", connect_timeout=3
        )
        mock_conn.close.assert_called_once()

    def test_connection_failure_returns_false(self):
        """Connection failure returns False."""
        pg_provider.psycopg2.connect.reset_mock()
        pg_provider.psycopg2.connect.side_effect = Exception("Connection refused")

        result = pg_provider.is_available("postgresql://localhost/test")
        self.assertFalse(result)

        # Reset side_effect for other tests
        pg_provider.psycopg2.connect.side_effect = None


class TestPgProviderFetchLearnings(unittest.TestCase):
    """Test fetch_learnings() function."""

    def setUp(self):
        """Reset mock state before each test."""
        pg_provider.psycopg2.connect.reset_mock()
        pg_provider.psycopg2.connect.side_effect = None

    def _make_row(self, learning_id=None, content="test content", learning_type="WORKING_SOLUTION"):
        """Create a mock database row."""
        if learning_id is None:
            learning_id = str(uuid4())
        return {
            "id": learning_id,
            "content": content,
            "metadata": {
                "type": "session_learning",
                "learning_type": learning_type,
                "session_id": "test-session",
                "context": "test context",
                "tags": ["test", "mock"],
                "confidence": "high",
                "timestamp": "2026-02-06T12:00:00",
            },
            "created_at": datetime(2026, 2, 6, 12, 0, 0),
        }

    def test_fetch_returns_learnings(self):
        """fetch_learnings returns properly formatted learning dicts."""
        row = self._make_row()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [row]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        pg_provider.psycopg2.connect.return_value = mock_conn

        results = pg_provider.fetch_learnings("postgresql://localhost/test", limit=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["content"], "test content")
        self.assertIn("metadata", results[0])
        self.assertIn("id", results[0])

    def test_fetch_with_since_parameter(self):
        """fetch_learnings passes since parameter to query."""
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        pg_provider.psycopg2.connect.return_value = mock_conn

        pg_provider.fetch_learnings("postgresql://localhost/test", since="2026-01-01T00:00:00")

        call_args = mock_cur.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        self.assertIn("AND created_at > %s", query)
        self.assertEqual(params[0], "2026-01-01T00:00:00")

    def test_fetch_no_psycopg2_returns_empty(self):
        """Without psycopg2, fetch returns empty list."""
        original = pg_provider.HAS_PSYCOPG2
        try:
            pg_provider.HAS_PSYCOPG2 = False
            results = pg_provider.fetch_learnings("postgresql://localhost/test")
            self.assertEqual(results, [])
        finally:
            pg_provider.HAS_PSYCOPG2 = original

    def test_fetch_db_error_returns_empty(self):
        """Database errors return empty list, not exceptions."""
        pg_provider.psycopg2.connect.side_effect = Exception("DB error")
        results = pg_provider.fetch_learnings("postgresql://localhost/test")
        self.assertEqual(results, [])


class TestPgProviderFetchLearningContent(unittest.TestCase):
    """Test fetch_learning_content() function."""

    def setUp(self):
        pg_provider.psycopg2.connect.reset_mock()
        pg_provider.psycopg2.connect.side_effect = None

    def test_fetch_content_formats_correctly(self):
        """fetch_learning_content returns well-formatted content string."""
        row = {
            "content": "This is the learning content",
            "metadata": {
                "learning_type": "ERROR_FIX",
                "context": "debugging hooks",
                "confidence": "high",
                "tags": ["hooks", "error"],
                "session_id": "debug-session",
            },
            "created_at": datetime(2026, 2, 6, 12, 0, 0),
        }
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = row
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        pg_provider.psycopg2.connect.return_value = mock_conn

        result = pg_provider.fetch_learning_content("postgresql://localhost/test", "some-uuid")

        self.assertIn("Type: ERROR_FIX", result)
        self.assertIn("Context: debugging hooks", result)
        self.assertIn("Confidence: high", result)
        self.assertIn("Tags: hooks, error", result)
        self.assertIn("This is the learning content", result)
        self.assertIn("---", result)

    def test_fetch_content_not_found(self):
        """Returns empty string when learning not found."""
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        pg_provider.psycopg2.connect.return_value = mock_conn

        result = pg_provider.fetch_learning_content("postgresql://localhost/test", "bad-uuid")
        self.assertEqual(result, "")

    def test_fetch_content_no_psycopg2(self):
        """Without psycopg2, returns empty string."""
        original = pg_provider.HAS_PSYCOPG2
        try:
            pg_provider.HAS_PSYCOPG2 = False
            result = pg_provider.fetch_learning_content("postgresql://localhost/test", "some-uuid")
            self.assertEqual(result, "")
        finally:
            pg_provider.HAS_PSYCOPG2 = original

    def test_fetch_content_empty_id(self):
        """Empty learning_id returns empty string."""
        result = pg_provider.fetch_learning_content("postgresql://localhost/test", "")
        self.assertEqual(result, "")


class TestPgProviderLearningToEntry(unittest.TestCase):
    """Test learning_to_index_entry() function."""

    def _dummy_extract_keywords(self, content, frontmatter):
        """Simple keyword extractor for testing."""
        words = content.lower().split()
        return [w for w in words if len(w) > 3][:10]

    def test_converts_learning_to_entry(self):
        """learning_to_index_entry produces correct BloxCue entry format."""
        learning = {
            "id": "test-uuid-123",
            "content": "TypeScript hooks require npm install before they work",
            "metadata": {
                "learning_type": "WORKING_SOLUTION",
                "context": "hook development",
                "tags": ["hooks", "typescript"],
                "confidence": "high",
                "session_id": "test-session",
            },
            "created_at": "2026-02-06T12:00:00",
        }

        entry = pg_provider.learning_to_index_entry(learning, self._dummy_extract_keywords)

        self.assertIsNotNone(entry)
        self.assertEqual(entry["path"], "pg://learning/test-uuid-123")
        self.assertEqual(entry["source"], "pg")
        self.assertEqual(entry["category"], "learnings/solution")
        self.assertIn("hooks", entry["tags"])
        self.assertIn("typescript", entry["tags"])
        self.assertIn("working_solution", entry["tags"])
        self.assertIn("confidence:high", entry["tags"])
        self.assertIn("[PG]", entry["title"])
        self.assertIn("hook development", entry["title"])
        self.assertEqual(entry["size"], len(learning["content"]))
        self.assertTrue(len(entry["preview"]) > 0)

    def test_empty_content_returns_none(self):
        """Learning with empty content returns None."""
        learning = {"id": "uuid", "content": "", "metadata": {}, "created_at": ""}
        entry = pg_provider.learning_to_index_entry(learning, self._dummy_extract_keywords)
        self.assertIsNone(entry)

    def test_unknown_learning_type(self):
        """Unknown learning_type maps to learnings/other."""
        learning = {
            "id": "uuid",
            "content": "some content here",
            "metadata": {"learning_type": "CUSTOM_TYPE"},
            "created_at": "",
        }
        entry = pg_provider.learning_to_index_entry(learning, self._dummy_extract_keywords)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["category"], "learnings/other")

    def test_no_context_in_title(self):
        """Learning without context uses just type label in title."""
        learning = {
            "id": "uuid",
            "content": "some content",
            "metadata": {"learning_type": "ERROR_FIX"},
            "created_at": "",
        }
        entry = pg_provider.learning_to_index_entry(learning, self._dummy_extract_keywords)
        self.assertEqual(entry["title"], "[PG] Error Fix")


# ============================================================
# Integration tests (indexer + pg_provider)
# ============================================================

class TestIndexerPgIntegration(unittest.TestCase):
    """Test indexer.py integration with pg_provider."""

    def setUp(self):
        """Reset indexer module state."""
        import indexer
        indexer._index_cache = None
        indexer._index_mtime = None

    def _make_learning(self, learning_id="uuid-1", content="Test learning content",
                       learning_type="WORKING_SOLUTION", context="test"):
        return {
            "id": learning_id,
            "content": content,
            "metadata": {
                "type": "session_learning",
                "learning_type": learning_type,
                "context": context,
                "tags": ["test"],
                "confidence": "high",
            },
            "created_at": "2026-02-06T12:00:00",
        }

    @patch("indexer.PG_ENABLED", True)
    @patch("indexer.PG_DATABASE_URL", "postgresql://localhost/test")
    @patch("indexer.HAS_PG_PROVIDER", True)
    @patch("indexer.pg_is_available", return_value=True)
    @patch("indexer.pg_fetch_learnings")
    @patch("indexer.pg_learning_to_entry")
    def test_build_index_merges_pg_entries(self, mock_to_entry, mock_fetch, mock_available):
        """build_index() merges PG learnings into the index."""
        import indexer

        learning = self._make_learning()
        mock_fetch.return_value = [learning]
        mock_to_entry.return_value = {
            "path": "pg://learning/uuid-1",
            "title": "[PG] Working Solution: test",
            "category": "learnings/solution",
            "tags": ["test", "working_solution"],
            "keywords": ["test", "learning"],
            "bigrams": [],
            "size": 100,
            "modified": "2026-02-06T12:00:00",
            "preview": "Test learning content",
            "source": "pg",
        }

        index = indexer.build_index()

        # Should have PG entry in files
        pg_entries = [f for f in index["files"] if f.get("source") == "pg"]
        self.assertTrue(len(pg_entries) > 0)
        self.assertEqual(pg_entries[0]["path"], "pg://learning/uuid-1")
        self.assertIn("pg_fetched_at", index)

    @patch("indexer.PG_ENABLED", True)
    @patch("indexer.PG_DATABASE_URL", "postgresql://localhost/test")
    @patch("indexer.HAS_PG_PROVIDER", True)
    @patch("indexer.pg_is_available", return_value=True)
    @patch("indexer.pg_fetch_learnings")
    @patch("indexer.pg_learning_to_entry")
    def test_build_index_deduplicates_pg_entries(self, mock_to_entry, mock_fetch, mock_available):
        """build_index() doesn't duplicate PG entries on rebuild."""
        import indexer

        entry = {
            "path": "pg://learning/uuid-1",
            "title": "[PG] Test",
            "category": "learnings/solution",
            "tags": [],
            "keywords": [],
            "bigrams": [],
            "size": 50,
            "modified": "",
            "preview": "test",
            "source": "pg",
        }
        mock_fetch.return_value = [self._make_learning(), self._make_learning()]
        mock_to_entry.return_value = entry

        index = indexer.build_index()

        pg_entries = [f for f in index["files"] if f.get("path") == "pg://learning/uuid-1"]
        self.assertEqual(len(pg_entries), 1, "Should deduplicate PG entries with same path")

    @patch("indexer.PG_ENABLED", False)
    @patch("indexer.HAS_PG_PROVIDER", True)
    def test_build_index_pg_disabled(self):
        """build_index() skips PG when PG_ENABLED=False."""
        import indexer
        index = indexer.build_index()
        self.assertNotIn("pg_fetched_at", index)


class TestGetFileContentPgRouting(unittest.TestCase):
    """Test get_file_content() routing for pg:// paths."""

    @patch("indexer.PG_ENABLED", True)
    @patch("indexer.PG_DATABASE_URL", "postgresql://localhost/test")
    @patch("indexer.HAS_PG_PROVIDER", True)
    @patch("indexer.pg_fetch_learning_content", return_value="Learning content here")
    def test_pg_path_routes_to_provider(self, mock_fetch):
        """pg:// paths route to pg_fetch_learning_content."""
        import indexer
        result = indexer.get_file_content("pg://learning/some-uuid")
        self.assertEqual(result, "Learning content here")
        mock_fetch.assert_called_once_with("postgresql://localhost/test", "some-uuid")

    @patch("indexer.PG_ENABLED", False)
    @patch("indexer.HAS_PG_PROVIDER", True)
    def test_pg_path_disabled_returns_empty(self):
        """pg:// paths return empty when PG disabled."""
        import indexer
        result = indexer.get_file_content("pg://learning/some-uuid")
        self.assertEqual(result, "")

    def test_regular_path_unchanged(self):
        """Regular file paths still work normally."""
        import indexer
        result = indexer.get_file_content("nonexistent/file.md")
        self.assertEqual(result, "")


class TestDisplayResultsPgGuard(unittest.TestCase):
    """Test display_results() handles pg:// paths without crashing."""

    def test_display_pg_results(self):
        """display_results doesn't crash on pg:// entries."""
        import indexer
        results = [{
            "entry": {
                "path": "pg://learning/uuid-1",
                "title": "[PG] Test Learning",
                "category": "learnings/solution",
                "tags": ["test"],
                "preview": "Some preview",
                "source": "pg",
            },
            "score": 5.0,
        }]
        indexer.display_results(results, verbose=True)

    def test_display_mixed_results(self):
        """display_results handles mix of file and PG results."""
        import indexer
        results = [
            {
                "entry": {
                    "path": "guides/test.md",
                    "title": "Test Guide",
                    "category": "guides",
                    "tags": [],
                    "preview": "File preview",
                },
                "score": 8.0,
            },
            {
                "entry": {
                    "path": "pg://learning/uuid-1",
                    "title": "[PG] Test Learning",
                    "category": "learnings/solution",
                    "tags": ["test"],
                    "preview": "PG preview",
                    "source": "pg",
                },
                "score": 5.0,
            },
        ]
        indexer.display_results(results, verbose=True)


# ============================================================
# Fallback tests
# ============================================================

class TestPgFallbacks(unittest.TestCase):
    """Test graceful degradation when PG is unavailable."""

    @patch("indexer.PG_ENABLED", True)
    @patch("indexer.PG_DATABASE_URL", "postgresql://localhost/test")
    @patch("indexer.HAS_PG_PROVIDER", True)
    @patch("indexer.pg_is_available", return_value=False)
    def test_pg_unavailable_file_only(self, mock_available):
        """When PG is unreachable, build_index still works with files only."""
        import indexer
        index = indexer.build_index()
        self.assertNotIn("pg_fetched_at", index)
        self.assertIn("files", index)

    @patch("indexer.HAS_PG_PROVIDER", False)
    @patch("indexer.PG_ENABLED", True)
    def test_no_pg_provider_module(self):
        """When pg_provider module missing, build_index works normally."""
        import indexer
        index = indexer.build_index()
        self.assertIn("files", index)
        self.assertNotIn("pg_fetched_at", index)

    @patch("indexer.PG_ENABLED", True)
    @patch("indexer.PG_DATABASE_URL", "postgresql://localhost/test")
    @patch("indexer.HAS_PG_PROVIDER", True)
    @patch("indexer.pg_is_available", return_value=True)
    @patch("indexer.pg_fetch_learnings", side_effect=Exception("DB crashed"))
    def test_pg_fetch_error_non_fatal(self, mock_fetch, mock_available):
        """PG fetch errors don't crash build_index."""
        import indexer
        index = indexer.build_index()
        self.assertIn("files", index)


class TestPgCacheTTL(unittest.TestCase):
    """Test PG cache TTL in load_index()."""

    def setUp(self):
        import indexer
        indexer._index_cache = None
        indexer._index_mtime = None

    @patch("indexer.PG_ENABLED", True)
    @patch("indexer.PG_CACHE_TTL", 300)
    @patch("indexer.HAS_PG_PROVIDER", True)
    def test_stale_pg_cache_triggers_rebuild(self):
        """When pg_fetched_at is older than TTL, load_index triggers rebuild."""
        import indexer

        stale_time = (datetime.now() - timedelta(seconds=600)).isoformat()
        fake_index = {
            "files": [],
            "built": datetime.now().isoformat(),
            "pg_fetched_at": stale_time,
            "idf": {},
            "doc_stats": {},
        }

        indexer._index_cache = fake_index
        indexer._index_mtime = 12345.0

        # Patch INDEX_FILE as a module-level attribute
        mock_index_file = MagicMock()
        mock_index_file.exists.return_value = True
        mock_index_file.stat.return_value = MagicMock(st_mtime=12345.0)

        with patch("indexer.INDEX_FILE", mock_index_file), \
             patch("indexer.build_index") as mock_build:
            mock_build.return_value = {"files": [], "built": "", "idf": {}, "doc_stats": {}}

            indexer.load_index()

            mock_build.assert_called_once()

    @patch("indexer.PG_ENABLED", True)
    @patch("indexer.PG_CACHE_TTL", 300)
    @patch("indexer.HAS_PG_PROVIDER", True)
    def test_fresh_pg_cache_uses_cache(self):
        """When pg_fetched_at is within TTL, load_index returns cache."""
        import indexer

        fresh_time = datetime.now().isoformat()
        fake_index = {
            "files": [],
            "built": datetime.now().isoformat(),
            "pg_fetched_at": fresh_time,
            "idf": {},
            "doc_stats": {},
        }

        indexer._index_cache = fake_index
        indexer._index_mtime = 12345.0

        mock_index_file = MagicMock()
        mock_index_file.exists.return_value = True
        mock_index_file.stat.return_value = MagicMock(st_mtime=12345.0)

        with patch("indexer.INDEX_FILE", mock_index_file), \
             patch("indexer.build_index") as mock_build:

            result = indexer.load_index()

            mock_build.assert_not_called()
            self.assertEqual(result, fake_index)


if __name__ == "__main__":
    unittest.main(verbosity=2)
