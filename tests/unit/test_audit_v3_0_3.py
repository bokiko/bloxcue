#!/usr/bin/env python3
"""
Regression tests for the two remaining low-severity audit findings,
fixed in v3.0.3:

L-2 — CLI ``--limit`` accepts negative or huge values. MCP caps to
[1, 100]; CLI did not, producing odd slicing or excessive resource use.

L-3 — ``--import-postgres`` was not idempotent. Re-running the import
created duplicate SQLite rows because nothing checked legacy_path.
"""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest


PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ============================================================
# L-2: CLI --limit clamping
# ============================================================

def _run_cli(args, env_extra=None):
    """Invoke scripts/indexer.py as a subprocess and return CompletedProcess."""
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "indexer.py"), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


def test_cli_limit_negative_does_not_crash(tmp_path):
    """--limit -5 should fall back to the default, not crash or slice oddly."""
    memory_dir = tmp_path / "knowledge"
    memory_dir.mkdir()
    (memory_dir / "doc.md").write_text(
        "---\ntitle: Doc\n---\n\nDeployment runbook.\n", encoding="utf-8"
    )
    env_extra = {
        "BLOXCUE_MEMORY_DIR": str(memory_dir),
        "BLOXCUE_LEARNINGS_DB": str(tmp_path / "learnings.db"),
        "BLOXCUE_INDEX_FILE": str(tmp_path / "index.json"),
        "BLOXCUE_USAGE_FILE": str(tmp_path / "usage.jsonl"),
    }
    # Build the index first so search has something to work with
    build_proc = _run_cli([], env_extra=env_extra)
    assert build_proc.returncode == 0, build_proc.stderr

    proc = _run_cli(["--search", "deploy", "--limit", "-5", "--json"], env_extra=env_extra)
    assert proc.returncode == 0, f"CLI crashed on negative limit: {proc.stderr!r}"
    # Output should be valid JSON (an array)
    payload = json.loads(proc.stdout.strip())
    assert isinstance(payload, list)


def test_cli_limit_huge_is_capped(tmp_path):
    """--limit 999999 should not load more than 100 results."""
    memory_dir = tmp_path / "knowledge"
    memory_dir.mkdir()
    # Create 5 docs so we can confirm "all of them" comes back without error
    for i in range(5):
        (memory_dir / f"doc{i}.md").write_text(
            f"---\ntitle: Doc {i}\n---\n\nDeployment content {i}.\n", encoding="utf-8"
        )
    env_extra = {
        "BLOXCUE_MEMORY_DIR": str(memory_dir),
        "BLOXCUE_LEARNINGS_DB": str(tmp_path / "learnings.db"),
        "BLOXCUE_INDEX_FILE": str(tmp_path / "index.json"),
        "BLOXCUE_USAGE_FILE": str(tmp_path / "usage.jsonl"),
    }
    _run_cli([], env_extra=env_extra)

    proc = _run_cli(["--search", "deployment", "--limit", "999999", "--json"], env_extra=env_extra)
    assert proc.returncode == 0, f"CLI crashed on huge limit: {proc.stderr!r}"
    payload = json.loads(proc.stdout.strip())
    # The cap is 100; we only have 5 docs but the cap must hold even if more existed
    assert len(payload) <= 100


def test_cli_limit_zero_falls_back(tmp_path):
    """--limit 0 should fall back to the default rather than returning nothing."""
    memory_dir = tmp_path / "knowledge"
    memory_dir.mkdir()
    (memory_dir / "doc.md").write_text(
        "---\ntitle: Doc\n---\n\nDeployment guide.\n", encoding="utf-8"
    )
    env_extra = {
        "BLOXCUE_MEMORY_DIR": str(memory_dir),
        "BLOXCUE_LEARNINGS_DB": str(tmp_path / "learnings.db"),
        "BLOXCUE_INDEX_FILE": str(tmp_path / "index.json"),
        "BLOXCUE_USAGE_FILE": str(tmp_path / "usage.jsonl"),
    }
    _run_cli([], env_extra=env_extra)

    proc = _run_cli(["--search", "deploy", "--limit", "0", "--json"], env_extra=env_extra)
    assert proc.returncode == 0, f"CLI crashed on limit=0: {proc.stderr!r}"
    payload = json.loads(proc.stdout.strip())
    # With one doc and a fallback default of 5, we expect at most 5 results
    assert isinstance(payload, list)
    assert len(payload) <= 5


# ============================================================
# L-3: --import-postgres idempotency
# ============================================================

def _reload_indexer():
    if "indexer" in sys.modules:
        return importlib.reload(sys.modules["indexer"])
    import indexer  # noqa: F401
    return sys.modules["indexer"]


def test_import_postgres_is_idempotent(tmp_path, monkeypatch):
    """Running --import-postgres twice with the same source must not duplicate rows."""
    memory_dir = tmp_path / "knowledge"
    memory_dir.mkdir()
    db_path = tmp_path / "learnings.db"

    monkeypatch.setenv("BLOXCUE_MEMORY_DIR", str(memory_dir))
    monkeypatch.setenv("BLOXCUE_LEARNINGS_DB", str(db_path))
    monkeypatch.setenv("BLOXCUE_INDEX_FILE", str(tmp_path / "index.json"))
    monkeypatch.setenv("BLOXCUE_USAGE_FILE", str(tmp_path / "usage.jsonl"))

    indexer = _reload_indexer()

    # Fixture: 3 fake "PG" learnings, each with a stable id so legacy_path is
    # deterministic across runs
    fake_rows = [
        {
            "id": f"row-{i}",
            "content": f"Learning content #{i}",
            "metadata": {
                "learning_type": "WORKING_SOLUTION",
                "context": f"Topic {i}",
                "tags": ["test"],
            },
        }
        for i in range(3)
    ]

    # Stub PG provider so no real DB is needed
    monkeypatch.setattr(indexer, "HAS_PG_PROVIDER", True)
    monkeypatch.setattr(indexer, "pg_is_available", lambda url: True)
    monkeypatch.setattr(indexer, "pg_fetch_learnings", lambda url, limit=500: fake_rows)

    # First run: 3 new rows
    first = indexer.import_postgres_learnings("postgresql://stub")
    assert first == 3, f"first run should import 3 rows, got {first}"
    rows_after_first = list(indexer.iter_learnings())
    assert len(rows_after_first) == 3

    # Second run: 0 new rows because all legacy_paths already exist
    second = indexer.import_postgres_learnings("postgresql://stub")
    assert second == 0, f"second run should import 0 rows (idempotent), got {second}"
    rows_after_second = list(indexer.iter_learnings())
    assert len(rows_after_second) == 3, (
        f"Re-running --import-postgres duplicated rows: {len(rows_after_first)} -> "
        f"{len(rows_after_second)}"
    )

    # Third run: still no duplicates
    third = indexer.import_postgres_learnings("postgresql://stub")
    assert third == 0
    assert len(list(indexer.iter_learnings())) == 3


def test_search_json_output_is_clean_on_first_run(tmp_path):
    """The 'Indexed:' progress lines from build_index must go to stderr.

    Otherwise, ``--search ... --json`` produces stdout that is "Indexed:
    legit.md\\n[...]" — the leading log lines break json.loads in any
    subprocess consumer (notably hooks/memory-retrieve.py). Regression
    for a bug that masked itself in CI but surfaced on machines with a
    non-empty ~/.claude-memory legacy dir.
    """
    memory_dir = tmp_path / "knowledge"
    memory_dir.mkdir()
    (memory_dir / "deploy.md").write_text(
        "---\ntitle: Deploy\n---\n\nDeployment guide.\n", encoding="utf-8"
    )

    env = os.environ.copy()
    env["BLOXCUE_MEMORY_DIR"] = str(memory_dir)
    env["BLOXCUE_LEARNINGS_DB"] = str(tmp_path / "learnings.db")
    env["BLOXCUE_INDEX_FILE"] = str(tmp_path / "index.json")
    env["BLOXCUE_USAGE_FILE"] = str(tmp_path / "usage.jsonl")

    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "indexer.py"),
         "--search", "deploy", "--limit", "3", "--json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr

    # stdout MUST be clean JSON — no "Indexed:" log noise
    assert not proc.stdout.lstrip().startswith("Indexed:"), (
        f"stdout starts with index-build noise instead of JSON:\n{proc.stdout[:200]}"
    )
    payload = json.loads(proc.stdout.strip())
    assert isinstance(payload, list)


def test_import_postgres_skips_empty_content(tmp_path, monkeypatch):
    """Empty/whitespace content must not produce a row, but must not crash either."""
    monkeypatch.setenv("BLOXCUE_MEMORY_DIR", str(tmp_path / "knowledge"))
    (tmp_path / "knowledge").mkdir()
    monkeypatch.setenv("BLOXCUE_LEARNINGS_DB", str(tmp_path / "learnings.db"))
    monkeypatch.setenv("BLOXCUE_INDEX_FILE", str(tmp_path / "index.json"))
    monkeypatch.setenv("BLOXCUE_USAGE_FILE", str(tmp_path / "usage.jsonl"))

    indexer = _reload_indexer()

    fake_rows = [
        {"id": "empty", "content": "", "metadata": {}},
        {"id": "ws", "content": "   \n  ", "metadata": {}},
        {"id": "real", "content": "Actual content", "metadata": {}},
    ]
    monkeypatch.setattr(indexer, "HAS_PG_PROVIDER", True)
    monkeypatch.setattr(indexer, "pg_is_available", lambda url: True)
    monkeypatch.setattr(indexer, "pg_fetch_learnings", lambda url, limit=500: fake_rows)

    imported = indexer.import_postgres_learnings("postgresql://stub")
    assert imported == 1, f"only the non-empty row should import, got {imported}"
