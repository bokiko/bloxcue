#!/usr/bin/env python3
"""
BloxCue Claude Code UserPromptSubmit hook.

Reads Claude Code hook JSON from stdin, searches BloxCue with shell=False, and
emits Claude hook JSON on stdout.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


MEMORY_PATH = Path(os.environ.get("BLOXCUE_MEMORY_DIR", str(Path.home() / ".bloxcue" / "knowledge"))).expanduser()


def _safe_int(name: str, default: int) -> int:
    """Parse an env var as int, falling back to default on garbage values.

    v3.0.1: previously a malformed BLOXCUE_HOOK_* env var would raise
    ValueError at module import, before main() could emit the JSON
    payload Claude Code expects. Mirrors the safe-parse pattern the
    indexer already uses for BLOXCUE_MAX_TOKENS.
    """
    try:
        return int(os.environ.get(name, str(default)))
    except (ValueError, TypeError):
        return default


MAX_RESULTS = _safe_int("BLOXCUE_HOOK_MAX_RESULTS", 3)
MAX_CONTEXT_CHARS = _safe_int("BLOXCUE_HOOK_MAX_CONTEXT_CHARS", 3000)
MIN_QUERY_LENGTH = _safe_int("BLOXCUE_HOOK_MIN_QUERY_LENGTH", 5)


def emit(message=None):
    payload = {"result": "continue"}
    if message:
        payload["message"] = message
    print(json.dumps(payload))


def sanitize_prompt(value):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", value)
    return value[:500].strip()


def should_skip(prompt):
    if len(prompt) < MIN_QUERY_LENGTH:
        return True
    lower = " ".join(prompt.lower().split())
    skip_patterns = [
        r"^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|sure|got it)$",
        r"^(what|how|why|can you|could you|please|help)$",
        r"^[0-9]+$",
    ]
    return any(re.search(pattern, lower) for pattern in skip_patterns)


def indexer_path():
    local = MEMORY_PATH / "scripts" / "indexer.py"
    if local.exists():
        return local
    repo = Path(__file__).resolve().parents[1] / "scripts" / "indexer.py"
    if repo.exists():
        return repo
    return local


def build_context(results):
    output = []
    total_chars = 0
    for result in results:
        if result.get("score", 0) <= 5:
            continue
        title = result.get("title", "Unknown")
        path = result.get("path", "")
        content = result.get("content", "")
        score = result.get("score", 0)
        if score > 20:
            max_content = 800
        elif score > 10:
            max_content = 500
        else:
            max_content = 300
        snippet = content[:max_content]
        if len(content) > max_content:
            snippet += "..."
        entry = f"### {title}\n*Source: {path}*\n\n{snippet}\n"
        if total_chars + len(entry) > MAX_CONTEXT_CHARS:
            break
        output.append(entry)
        total_chars += len(entry)
    if not output:
        return ""
    return "Relevant context from BloxCue:\n\n" + "\n---\n".join(output)


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        emit()
        return

    prompt = sanitize_prompt(payload.get("user_prompt", ""))
    if should_skip(prompt):
        emit()
        return

    indexer = indexer_path()
    if not indexer.exists():
        emit()
        return

    env = os.environ.copy()
    env.setdefault("BLOXCUE_MEMORY_DIR", str(MEMORY_PATH))
    try:
        completed = subprocess.run(
            [sys.executable, str(indexer), "--search", prompt, "--limit", str(MAX_RESULTS), "--json"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        emit()
        return

    if completed.returncode != 0:
        emit()
        return

    try:
        results = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        emit()
        return

    emit(build_context(results))


if __name__ == "__main__":
    main()
