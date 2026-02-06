#!/usr/bin/env python3
"""
BloxCue PostgreSQL Provider

Fetches learnings from OpenClaw's PostgreSQL database and converts them
to BloxCue index entries. All PostgreSQL interaction is isolated here.

Design:
- psycopg2 is optional: missing → HAS_PSYCOPG2=False, all functions return empty
- Every PG call wrapped in try/except, errors logged to stderr
- Learnings get pg://learning/{uuid} virtual paths
- source: "pg" field distinguishes from file entries
"""

import sys
import json
from datetime import datetime
from typing import Callable, Dict, List, Optional

# Optional psycopg2 import
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


# Learning type → BloxCue category mapping
LEARNING_TYPE_CATEGORIES = {
    "WORKING_SOLUTION": "learnings/solution",
    "ERROR_FIX": "learnings/fix",
    "ARCHITECTURAL_DECISION": "learnings/architecture",
    "CODEBASE_PATTERN": "learnings/pattern",
    "FAILED_APPROACH": "learnings/failed",
    "USER_PREFERENCE": "learnings/preference",
    "OPEN_THREAD": "learnings/thread",
}


def is_available(url: str) -> bool:
    """Check if PostgreSQL is reachable with the given URL.

    Returns False if psycopg2 is missing or connection fails.
    """
    if not HAS_PSYCOPG2 or not url:
        return False

    try:
        conn = psycopg2.connect(url, connect_timeout=3)
        conn.close()
        return True
    except Exception as e:
        print(f"[BloxCue PG] Connection check failed: {e}", file=sys.stderr)
        return False


def fetch_learnings(url: str, limit: int = 500, since: Optional[str] = None) -> List[Dict]:
    """Fetch session learnings from the archival_memory table.

    Args:
        url: PostgreSQL connection URL
        limit: Maximum learnings to fetch
        since: ISO timestamp - only fetch learnings newer than this

    Returns:
        List of learning dicts with keys: id, content, metadata, created_at
    """
    if not HAS_PSYCOPG2 or not url:
        return []

    try:
        conn = psycopg2.connect(url, connect_timeout=5)
        conn.set_session(readonly=True)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
            SELECT id, content, metadata, created_at
            FROM archival_memory
            WHERE metadata->>'type' = 'session_learning'
        """
        params: list = []

        if since:
            query += " AND created_at > %s"
            params.append(since)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()

        cur.close()
        conn.close()

        learnings = []
        for row in rows:
            learning = {
                "id": str(row["id"]),
                "content": row["content"] or "",
                "metadata": row["metadata"] if isinstance(row["metadata"], dict) else {},
                "created_at": row["created_at"].isoformat() if row["created_at"] else "",
            }
            learnings.append(learning)

        return learnings

    except Exception as e:
        print(f"[BloxCue PG] Failed to fetch learnings: {e}", file=sys.stderr)
        return []


def fetch_learning_content(url: str, learning_id: str) -> str:
    """Fetch the content of a single learning by ID.

    Args:
        url: PostgreSQL connection URL
        learning_id: UUID of the learning

    Returns:
        Learning content as formatted string, or empty string on failure
    """
    if not HAS_PSYCOPG2 or not url or not learning_id:
        return ""

    try:
        conn = psycopg2.connect(url, connect_timeout=5)
        conn.set_session(readonly=True)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            "SELECT content, metadata, created_at FROM archival_memory WHERE id = %s",
            (learning_id,)
        )
        row = cur.fetchone()

        cur.close()
        conn.close()

        if not row:
            return ""

        metadata = row["metadata"] if isinstance(row["metadata"], dict) else {}
        content = row["content"] or ""
        created_at = row["created_at"].isoformat() if row["created_at"] else "unknown"

        learning_type = metadata.get("learning_type", "UNKNOWN")
        context = metadata.get("context", "")
        confidence = metadata.get("confidence", "")
        tags = metadata.get("tags", [])
        session_id = metadata.get("session_id", "")

        lines = []
        lines.append(f"Type: {learning_type}")
        if context:
            lines.append(f"Context: {context}")
        if confidence:
            lines.append(f"Confidence: {confidence}")
        if tags:
            tags_str = ", ".join(str(t) for t in tags) if isinstance(tags, list) else str(tags)
            lines.append(f"Tags: {tags_str}")
        if session_id:
            lines.append(f"Session: {session_id}")
        lines.append(f"Created: {created_at}")
        lines.append("---")
        lines.append(content)

        return "\n".join(lines)

    except Exception as e:
        print(f"[BloxCue PG] Failed to fetch learning {learning_id}: {e}", file=sys.stderr)
        return ""


def learning_to_index_entry(learning: Dict, extract_keywords_fn: Callable) -> Optional[Dict]:
    """Convert a learning dict to a BloxCue index entry.

    Args:
        learning: Dict with keys: id, content, metadata, created_at
        extract_keywords_fn: Function(content, frontmatter) -> List[str]

    Returns:
        BloxCue index entry dict, or None if learning is empty/invalid
    """
    content = learning.get("content", "")
    if not content:
        return None

    metadata = learning.get("metadata", {})
    learning_id = learning.get("id", "")
    created_at = learning.get("created_at", "")

    learning_type = metadata.get("learning_type", "UNKNOWN")
    context = metadata.get("context", "")
    tags = metadata.get("tags", [])
    confidence = metadata.get("confidence", "medium")
    session_id = metadata.get("session_id", "")

    # Build title from type + context
    type_label = learning_type.replace("_", " ").title()
    if context:
        title = f"[PG] {type_label}: {context[:80]}"
    else:
        title = f"[PG] {type_label}"

    # Map learning_type to category
    category = LEARNING_TYPE_CATEGORIES.get(learning_type, "learnings/other")

    # Build tags list
    entry_tags = list(tags) if isinstance(tags, list) else []
    entry_tags.append(learning_type.lower())
    if confidence:
        entry_tags.append(f"confidence:{confidence}")

    # Build a synthetic frontmatter for keyword extraction
    frontmatter = {
        "title": title,
        "category": category,
        "tags": entry_tags,
    }

    keywords = extract_keywords_fn(content, frontmatter)

    # Build preview
    preview = content[:300].replace("\n", " ").strip()

    return {
        "path": f"pg://learning/{learning_id}",
        "title": title,
        "category": category,
        "tags": entry_tags,
        "keywords": keywords,
        "bigrams": [],  # PG learnings don't have structured headings for bigrams
        "size": len(content),
        "modified": created_at,
        "preview": preview,
        "source": "pg",
    }
