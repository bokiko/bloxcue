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
import ast
import json
import os
import subprocess
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
# Finding 1: Symlink indexing leak
# ============================================================

def test_symlink_to_outside_file_rejected(tmp_path, monkeypatch, reloadable_indexer):
    """A symlink inside MEMORY_DIR pointing to an external file must NOT be indexed."""
    # Build a fresh memory dir
    memory_dir = tmp_path / "knowledge"
    memory_dir.mkdir()

    # Legit file (should be indexed)
    legit = memory_dir / "legit.md"
    legit.write_text("---\ntitle: Legit\n---\n\nThis is a legitimate block.\n", encoding="utf-8")

    # External file with secret content
    external = tmp_path / "external_secret.md"
    external.write_text(
        "---\ntitle: SECRET\n---\n\nROOT_PASSWORD=hunter2_super_secret_marker\n",
        encoding="utf-8",
    )

    # Symlink inside memory dir pointing to the external file
    leak = memory_dir / "leak.md"
    leak.symlink_to(external)

    monkeypatch.setenv("BLOXCUE_MEMORY_DIR", str(memory_dir))
    monkeypatch.setenv("BLOXCUE_LEARNINGS_DB", str(tmp_path / "learnings.db"))
    monkeypatch.setenv("BLOXCUE_INDEX_FILE", str(tmp_path / "test_index.json"))
    monkeypatch.setenv("BLOXCUE_USAGE_FILE", str(tmp_path / "test_usage.jsonl"))

    indexer = reloadable_indexer()

    index = indexer.build_index()
    files = index.get("files", [])
    paths = [f.get("path", "") for f in files]
    previews = " ".join(f.get("preview", "") for f in files)

    # The leak file must not be indexed
    assert "leak.md" not in paths, f"Symlink to external file was indexed: {paths}"
    # The secret content must not appear anywhere in the index
    assert "hunter2_super_secret_marker" not in previews, (
        "External secret content leaked into index preview"
    )
    # The legit file should still be present
    assert any(p.endswith("legit.md") for p in paths), f"Legit file missing from index: {paths}"


def test_symlink_inside_memory_dir_allowed(tmp_path, monkeypatch, reloadable_indexer):
    """A symlink inside MEMORY_DIR pointing to another file inside MEMORY_DIR is legitimate."""
    memory_dir = tmp_path / "knowledge"
    memory_dir.mkdir()
    target = memory_dir / "target.md"
    target.write_text(
        "---\ntitle: Target\n---\n\nInternal content unique_internal_marker.\n",
        encoding="utf-8",
    )
    inside_link = memory_dir / "alias.md"
    inside_link.symlink_to(target)

    monkeypatch.setenv("BLOXCUE_MEMORY_DIR", str(memory_dir))
    monkeypatch.setenv("BLOXCUE_LEARNINGS_DB", str(tmp_path / "learnings.db"))
    monkeypatch.setenv("BLOXCUE_INDEX_FILE", str(tmp_path / "test_index.json"))
    monkeypatch.setenv("BLOXCUE_USAGE_FILE", str(tmp_path / "test_usage.jsonl"))

    indexer = reloadable_indexer()
    index = indexer.build_index()
    paths = [f.get("path", "") for f in index.get("files", [])]
    # At least the target should be indexed; the alias may or may not be present
    # depending on rglob behavior with symlinks, but neither should be rejected
    # for security reasons.
    assert any(p.endswith("target.md") for p in paths), (
        f"target.md should be indexed: {paths}"
    )


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


# ============================================================
# Finding 3: Atomic write replaces fcntl
# ============================================================

def test_atomic_write_no_partial_state(tmp_path, monkeypatch, reloadable_indexer):
    """If os.replace fails mid-write, the original index must remain intact."""
    memory_dir = tmp_path / "knowledge"
    memory_dir.mkdir()
    monkeypatch.setenv("BLOXCUE_MEMORY_DIR", str(memory_dir))
    monkeypatch.setenv("BLOXCUE_LEARNINGS_DB", str(tmp_path / "learnings.db"))
    monkeypatch.setenv("BLOXCUE_INDEX_FILE", str(tmp_path / "atomic_index.json"))
    monkeypatch.setenv("BLOXCUE_USAGE_FILE", str(tmp_path / "atomic_usage.jsonl"))

    indexer = reloadable_indexer()

    index_path = tmp_path / "atomic_index.json"
    # Pre-seed with known-good content
    original_data = {"files": [{"path": "original.md", "title": "Original"}]}
    indexer.write_index_safely(index_path, original_data)
    assert index_path.exists()
    pre_content = index_path.read_text()

    # Now patch os.replace to raise during the next write
    real_replace = os.replace

    def boom_replace(src, dst):
        raise OSError("simulated crash mid-write")

    monkeypatch.setattr("os.replace", boom_replace)

    new_data = {"files": [{"path": "new.md", "title": "New"}], "huge": "x" * 10000}
    with pytest.raises(OSError, match="simulated"):
        indexer.write_index_safely(index_path, new_data)

    # Original file untouched
    assert index_path.read_text() == pre_content, (
        "Original index must be intact when atomic write fails"
    )

    # Restore replace and verify next write succeeds
    monkeypatch.setattr("os.replace", real_replace)
    indexer.write_index_safely(index_path, new_data)
    assert json.loads(index_path.read_text())["files"][0]["path"] == "new.md"


def test_fcntl_no_longer_imported():
    """fcntl should not be imported by indexer.py anymore (Windows compat)."""
    import re
    indexer_source = (SCRIPTS_DIR / "indexer.py").read_text()
    assert not re.search(r"^\s*import\s+fcntl\b", indexer_source, re.MULTILINE), (
        "indexer.py still imports fcntl"
    )
    assert not re.search(r"^\s*from\s+fcntl\b", indexer_source, re.MULTILINE), (
        "indexer.py still uses 'from fcntl' import"
    )


# ============================================================
# Finding 4: Hook resilience to bad env vars
# ============================================================

def test_hook_with_bad_env_emits_continue(tmp_path):
    """memory-retrieve.py must emit valid JSON {"result": "continue"} even with bad env values."""
    hook = HOOKS_DIR / "memory-retrieve.py"
    assert hook.exists(), f"hook not found at {hook}"

    env = os.environ.copy()
    env["BLOXCUE_HOOK_MAX_RESULTS"] = "bad"
    env["BLOXCUE_HOOK_MAX_CONTEXT_CHARS"] = "garbage"
    env["BLOXCUE_HOOK_MIN_QUERY_LENGTH"] = "not-an-int"
    # Point at an empty memory dir so the hook doesn't try to do real work
    empty_dir = tmp_path / "empty_knowledge"
    empty_dir.mkdir()
    env["BLOXCUE_MEMORY_DIR"] = str(empty_dir)

    payload = json.dumps({"user_prompt": "hello world test query about indexing"})
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )

    assert proc.returncode == 0, (
        f"Hook exited non-zero with bad env vars. stderr={proc.stderr!r}, stdout={proc.stdout!r}"
    )
    # stdout must be parseable JSON with result=continue
    output = json.loads(proc.stdout.strip())
    assert output.get("result") == "continue", f"Expected continue, got {output}"


def test_shipped_python_files_parse_as_python38():
    """Docs promise Python 3.8+, so shipped scripts/hooks must avoid 3.9+ syntax."""
    files = sorted(SCRIPTS_DIR.glob("*.py")) + sorted(HOOKS_DIR.glob("*.py"))
    failures = []
    for path in files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 8))
        except SyntaxError as exc:
            failures.append(f"{path.relative_to(PROJECT_ROOT)}:{exc.lineno}: {exc.msg}")

    assert not failures, "Python 3.8 syntax failures:\n" + "\n".join(failures)
