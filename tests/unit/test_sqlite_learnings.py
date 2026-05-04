import importlib
import sys
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import indexer


def test_sqlite_learning_add_list_search(tmp_path, monkeypatch):
    db_path = tmp_path / "learnings.db"
    monkeypatch.setattr(indexer, "LEARNINGS_DB", db_path)
    monkeypatch.setattr(indexer, "_index_cache", None)
    monkeypatch.setattr(indexer, "_index_mtime", None)

    learning_id = indexer.add_learning(
        "Use sqlite learned memory for local records",
        title="SQLite learned memory",
        tags=["sqlite", "memory"],
    )

    rows = list(indexer.iter_learnings())
    assert len(rows) == 1
    assert rows[0]["id"] == learning_id

    built = indexer.build_index()
    paths = [entry["path"] for entry in built["files"]]
    assert f"memory://learning/{learning_id}" in paths

    results = indexer.search("sqlite memory", limit=5)
    assert any(r["entry"]["path"] == f"memory://learning/{learning_id}" for r in results)
    assert "Use sqlite learned memory" in indexer.get_file_content(f"memory://learning/{learning_id}")


def test_no_postgres_configured_is_valid(monkeypatch):
    monkeypatch.setattr(indexer, "PG_ENABLED", False)
    built = indexer.build_index()
    assert "files" in built


def test_continuous_claude_import_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "LEARNINGS_DB", tmp_path / "learnings.db")
    monkeypatch.setattr(indexer, "HAS_PG_PROVIDER", True)
    fixture = {
        "id": "uuid-1",
        "content": "Fixed auth token refresh by rotating the session cookie",
        "metadata": {
            "type": "session_learning",
            "learning_type": "ERROR_FIX",
            "context": "auth refresh",
            "tags": ["auth", "tokens"],
        },
        "created_at": "2026-02-06T12:00:00",
    }
    with patch.object(indexer, "pg_is_available", return_value=True), \
            patch.object(indexer, "pg_fetch_learnings", return_value=[fixture]):
        imported = indexer.import_postgres_learnings("postgresql://localhost/test")

    assert imported == 1
    rows = list(indexer.iter_learnings())
    assert len(rows) == 1
    assert rows[0]["legacy_path"] == "pg://learning/uuid-1"
    assert "auth token refresh" in rows[0]["content"]


def test_legacy_claude_memory_fallback(tmp_path, monkeypatch):
    primary = tmp_path / "bloxcue" / "knowledge"
    legacy = tmp_path / ".claude-memory"
    primary.mkdir(parents=True)
    legacy.mkdir()
    (legacy / "legacy-guide.md").write_text(
        """---
title: Legacy Guide
category: legacy
tags: [legacy, claude]
---

# Legacy Guide

Existing Claude memory remains searchable.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(indexer, "MEMORY_DIR", primary)
    monkeypatch.setattr(indexer, "LEGACY_MEMORY_DIR", legacy)
    monkeypatch.setattr(indexer, "INDEX_FILE", tmp_path / ".index.json")
    monkeypatch.setattr(indexer, "LEARNINGS_DB", tmp_path / "learnings.db")
    monkeypatch.setattr(indexer, "_index_cache", None)
    monkeypatch.setattr(indexer, "_index_mtime", None)

    built = indexer.build_index()

    assert any(entry["path"] == "legacy://claude-memory/legacy-guide.md" for entry in built["files"])
    assert "Existing Claude memory" in indexer.get_file_content("legacy://claude-memory/legacy-guide.md")


def test_default_memory_dir_repo_vs_installed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_scripts = repo_root / "scripts"
    repo_scripts.mkdir(parents=True)
    (repo_root / "templates").mkdir()
    monkeypatch.setattr(indexer, "SCRIPT_DIR", repo_scripts)
    assert indexer.default_memory_dir() == indexer.DEFAULT_MEMORY_DIR

    installed = tmp_path / "knowledge"
    installed_scripts = installed / "scripts"
    installed_scripts.mkdir(parents=True)
    monkeypatch.setattr(indexer, "SCRIPT_DIR", installed_scripts)
    assert indexer.default_memory_dir() == installed
