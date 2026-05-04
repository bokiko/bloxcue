#!/usr/bin/env python3
"""
Regression tests for v3.0.1 external code audit findings.

Findings:
1. HIGH - Symlink indexing leaks files outside memory root
2. HIGH - MCP and CLI use different index files (split-brain)
3. MEDIUM - Truncate-before-lock race in write_index_safely
4. MEDIUM - Hook crashes on bad env vars before emitting JSON
"""

import importlib
import os
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
HOOKS_DIR = PROJECT_ROOT / "hooks"
sys.path.insert(0, str(SCRIPTS_DIR))


def _reload_indexer():
    """Reload the indexer module so it picks up current environment."""
    if "indexer" in sys.modules:
        return importlib.reload(sys.modules["indexer"])
    import indexer  # noqa: F401
    return sys.modules["indexer"]


@pytest.fixture
def reloadable_indexer():
    """
    Reload indexer for the test, then restore the baseline (conftest)
    module state afterward so we don't poison sibling tests that read
    module-level INDEX_FILE / USAGE_FILE / MEMORY_DIR.

    pytest's monkeypatch fixture reverts env changes *after* this fixture
    finalizes, so we capture the relevant env vars here and restore them
    ourselves before the final reload.
    """
    keys = (
        "BLOXCUE_MEMORY_DIR",
        "BLOXCUE_LEARNINGS_DB",
        "BLOXCUE_INDEX_FILE",
        "BLOXCUE_USAGE_FILE",
    )
    saved = {k: os.environ.get(k) for k in keys}
    yield _reload_indexer
    # Restore env exactly as it was when the fixture started, then
    # reload the indexer so module-level constants (INDEX_FILE, etc.)
    # match the conftest baseline again.
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    _reload_indexer()


# ============================================================
# Finding 2: INDEX_FILE/USAGE_FILE under MEMORY_DIR
# ============================================================

def test_index_file_under_memory_dir(tmp_path, monkeypatch, reloadable_indexer):
    """INDEX_FILE and USAGE_FILE should default under MEMORY_DIR/.bloxcue, not SCRIPT_DIR."""
    memory_dir = tmp_path / "knowledge"
    memory_dir.mkdir()
    (memory_dir / "doc.md").write_text(
        "---\ntitle: Doc\n---\n\nContent.\n", encoding="utf-8"
    )

    monkeypatch.setenv("BLOXCUE_MEMORY_DIR", str(memory_dir))
    monkeypatch.setenv("BLOXCUE_LEARNINGS_DB", str(tmp_path / "learnings.db"))
    # Explicitly clear any override to test the *default* placement
    monkeypatch.delenv("BLOXCUE_INDEX_FILE", raising=False)
    monkeypatch.delenv("BLOXCUE_USAGE_FILE", raising=False)

    indexer = reloadable_indexer()

    expected_index = memory_dir / ".bloxcue" / "index.json"
    expected_usage = memory_dir / ".bloxcue" / "usage.jsonl"

    # INDEX_FILE should be inside MEMORY_DIR/.bloxcue/
    assert indexer.INDEX_FILE == expected_index, (
        f"INDEX_FILE should default to {expected_index}, got {indexer.INDEX_FILE}"
    )
    assert indexer.USAGE_FILE == expected_usage, (
        f"USAGE_FILE should default to {expected_usage}, got {indexer.USAGE_FILE}"
    )

    # And it must NOT be inside SCRIPT_DIR (the old location)
    script_dir = Path(indexer.__file__).parent.resolve()
    assert script_dir not in indexer.INDEX_FILE.resolve().parents, (
        f"INDEX_FILE leaked back into SCRIPT_DIR: {indexer.INDEX_FILE}"
    )

    # Build index and confirm the file actually lands at the expected path
    indexer.build_index()
    assert expected_index.exists(), f"Index file not created at {expected_index}"


def test_index_file_env_override(tmp_path, monkeypatch, reloadable_indexer):
    """BLOXCUE_INDEX_FILE and BLOXCUE_USAGE_FILE env vars should override defaults."""
    memory_dir = tmp_path / "knowledge"
    memory_dir.mkdir()
    custom_index = tmp_path / "my_custom_index.json"
    custom_usage = tmp_path / "my_custom_usage.jsonl"

    monkeypatch.setenv("BLOXCUE_MEMORY_DIR", str(memory_dir))
    monkeypatch.setenv("BLOXCUE_LEARNINGS_DB", str(tmp_path / "learnings.db"))
    monkeypatch.setenv("BLOXCUE_INDEX_FILE", str(custom_index))
    monkeypatch.setenv("BLOXCUE_USAGE_FILE", str(custom_usage))

    indexer = reloadable_indexer()
    assert indexer.INDEX_FILE == custom_index
    assert indexer.USAGE_FILE == custom_usage
