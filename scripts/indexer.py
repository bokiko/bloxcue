#!/usr/bin/env python3
"""
bloxcue Indexer

Index and search markdown context blocks for Claude Code.
Reduces token usage by enabling on-demand retrieval.

Usage:
    python3 indexer.py              # Index all files
    python3 indexer.py --search "query"  # Search indexed files
    python3 indexer.py --list       # List all indexed files
    python3 indexer.py --rebuild    # Force rebuild index
    python3 indexer.py --file path  # Index single file
"""

import os
import sys
import json
import re
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Set, Iterable

# PostgreSQL provider (optional)
try:
    from pg_provider import (
        is_available as pg_is_available,
        fetch_learnings as pg_fetch_learnings,
        fetch_learning_content as pg_fetch_learning_content,
        learning_to_index_entry as pg_learning_to_entry,
    )
    HAS_PG_PROVIDER = True
except ImportError:
    HAS_PG_PROVIDER = False

# Configuration
SCRIPT_DIR = Path(__file__).parent
DEFAULT_MEMORY_DIR = Path.home() / ".bloxcue" / "knowledge"
LEGACY_MEMORY_DIR = Path.home() / ".claude-memory"


def default_memory_dir() -> Path:
    """Resolve default memory dir for repo-run and installed-copy use."""
    installed_parent = SCRIPT_DIR.parent
    if not (installed_parent / "templates").exists():
        return installed_parent
    return DEFAULT_MEMORY_DIR


MEMORY_DIR = Path(os.environ.get("BLOXCUE_MEMORY_DIR", str(default_memory_dir()))).expanduser()

# v3.0.1: runtime state lives under MEMORY_DIR so the MCP server (repo copy)
# and the installed CLI copy share the same index when they share
# BLOXCUE_MEMORY_DIR. The old SCRIPT_DIR-based defaults caused MCP and CLI
# to write to different .index.json files and silently diverge.
_DEFAULT_STATE_DIR = MEMORY_DIR / ".bloxcue"
INDEX_FILE = Path(
    os.environ.get("BLOXCUE_INDEX_FILE", str(_DEFAULT_STATE_DIR / "index.json"))
).expanduser()
USAGE_FILE = Path(
    os.environ.get("BLOXCUE_USAGE_FILE", str(_DEFAULT_STATE_DIR / "usage.jsonl"))
).expanduser()
LEARNINGS_DB = Path(os.environ.get("BLOXCUE_LEARNINGS_DB", str(Path.home() / ".bloxcue" / "learnings.db"))).expanduser()
try:
    MAX_INJECT_TOKENS = int(os.environ.get("BLOXCUE_MAX_TOKENS", "3000"))
except (ValueError, TypeError):
    MAX_INJECT_TOKENS = 3000

# PostgreSQL import compatibility. Runtime PG merge is off by default in v3;
# use --import-postgres to copy archival_memory rows into SQLite.
PG_DATABASE_URL = os.environ.get("BLOXCUE_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
PG_ENABLED = bool(PG_DATABASE_URL) and os.environ.get("BLOXCUE_ENABLE_LEGACY_PG_RUNTIME", "0").lower() in ("1", "true", "yes", "on")
try:
    PG_CACHE_TTL = int(os.environ.get("BLOXCUE_PG_CACHE_TTL", "300"))
except (ValueError, TypeError):
    PG_CACHE_TTL = 300

# Stopwords - common words to ignore in search
STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
    'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare', 'ought',
    'used', 'it', 'its', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
    'she', 'we', 'they', 'what', 'which', 'who', 'whom', 'how', 'when', 'where',
    'why', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
    'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
    'too', 'very', 'just', 'also', 'now', 'here', 'there', 'then', 'once',
    'my', 'your', 'his', 'her', 'our', 'their', 'me', 'him', 'us', 'them',
    'if', 'else', 'elif', 'while', 'until', 'unless', 'although', 'because',
    'since', 'about', 'into', 'through', 'during', 'before', 'after', 'above',
    'below', 'between', 'under', 'again', 'further', 'any', 'get', 'got',
    'use', 'using', 'make', 'makes', 'made', 'way', 'ways', 'want', 'wants',
    'like', 'just', 'know', 'take', 'come', 'see', 'look', 'think', 'back',
    'yeah', 'yes', 'yeah', 'okay', 'ok', 'well', 'right', 'good', 'going',
}

# Intent patterns for query classification
INTENT_PATTERNS = {
    "howto": {
        "prefixes": ["how to", "how do i", "how can i", "steps to", "guide to"],
        "keywords": ["setup", "configure", "install", "create", "make", "build"],
        "weight_adjustments": {"tags": 1.5, "keywords": 1.3}
    },
    "troubleshoot": {
        "prefixes": ["why does", "why is", "fix", "error", "problem", "issue"],
        "keywords": ["failing", "broken", "not working", "crash", "bug"],
        "weight_adjustments": {"tags": 1.5, "preview": 2.0}
    },
    "concept": {
        "prefixes": ["what is", "what are", "explain", "describe", "define"],
        "keywords": ["concept", "theory", "overview", "introduction"],
        "weight_adjustments": {"title": 1.5, "category": 1.3}
    },
    "reference": {
        "prefixes": ["list of", "api", "reference", "syntax"],
        "keywords": ["documentation", "spec", "schema", "format"],
        "weight_adjustments": {"tags": 1.3, "category": 1.5}
    }
}


def detect_query_intent(query: str) -> Tuple[str, Dict[str, float]]:
    """
    Detect query intent and return weight adjustments.
    Returns (intent_name, weight_adjustments_dict).
    """
    if not isinstance(query, str):
        return "general", {}
    query_lower = query.lower()

    for intent, patterns in INTENT_PATTERNS.items():
        # Check prefixes
        for prefix in patterns["prefixes"]:
            if query_lower.startswith(prefix):
                return intent, patterns["weight_adjustments"]

        # Check keywords
        for keyword in patterns["keywords"]:
            if keyword in query_lower:
                return intent, patterns["weight_adjustments"]

    return "general", {}  # Default: no adjustments


# Synonym map for query expansion (common tech terms)
SYNONYM_MAP = {
    "db": ["database"],
    "database": ["db"],
    "api": ["endpoint", "rest"],
    "endpoint": ["api", "route"],
    "auth": ["authentication", "login"],
    "authentication": ["auth", "login"],
    "login": ["auth", "signin"],
    "config": ["configuration", "settings"],
    "configuration": ["config", "settings"],
    "deploy": ["deployment", "release"],
    "deployment": ["deploy", "release"],
    "ci": ["continuous integration", "pipeline"],
    "cd": ["continuous deployment", "pipeline"],
    "docker": ["container", "containerize"],
    "container": ["docker"],
    "k8s": ["kubernetes"],
    "kubernetes": ["k8s"],
    "env": ["environment"],
    "repo": ["repository"],
    "deps": ["dependencies"],
    "infra": ["infrastructure"],
    "frontend": ["ui", "client"],
    "backend": ["server", "api"],
    "test": ["testing", "spec"],
    "bug": ["error", "issue", "defect"],
    "error": ["bug", "exception", "failure"],
    "fix": ["patch", "resolve", "repair"],
    "setup": ["install", "configure"],
    "install": ["setup", "configure"],
    "migrate": ["migration", "upgrade"],
    "perf": ["performance"],
    "sec": ["security"],
    "docs": ["documentation"],
    "doc": ["documentation"],
}


def expand_query(terms: List[str], max_expansions: int = 3) -> List[Tuple[str, float]]:
    """
    Expand query terms with synonyms/acronyms.
    Returns list of (term, weight) tuples. Original terms get weight 1.0,
    expanded terms get weight 0.4 (lower to avoid diluting relevance).
    """
    expanded: List[Tuple[str, float]] = []

    for term in terms:
        expanded.append((term, 1.0))
        synonyms = SYNONYM_MAP.get(term, [])
        for syn in synonyms[:max_expansions]:
            # Stem the synonym for matching
            stemmed_syn = porter_stem(syn)
            if stemmed_syn and stemmed_syn != porter_stem(term):
                expanded.append((stemmed_syn, 0.4))

    return expanded


def normalize_word(word: str) -> str:
    """Normalize a word for comparison (lowercase, strip punctuation)."""
    if not isinstance(word, str):
        return ""
    return re.sub(r'[^\w]', '', word.lower())


# =============================================================================
# Porter Stemmer Implementation
# =============================================================================

def _is_consonant(word: str, i: int) -> bool:
    """Check if character at position i is a consonant."""
    if i >= len(word):
        return False
    c = word[i]
    if c in 'aeiou':
        return False
    if c == 'y':
        if i == 0:
            return True
        return not _is_consonant(word, i - 1)
    return True


def _measure(stem: str) -> int:
    """
    Count VC (vowel-consonant) sequences in stem.
    m=0: tr, ee, tree, y, by
    m=1: trouble, oats, trees, ivy
    m=2: troubles, private, oaten, orrery
    """
    m = 0
    i = 0
    n = len(stem)

    # Skip initial consonants
    while i < n and _is_consonant(stem, i):
        i += 1

    while i < n:
        # Count vowels
        while i < n and not _is_consonant(stem, i):
            i += 1
        if i >= n:
            break

        # Found end of vowel sequence, now count consonants
        while i < n and _is_consonant(stem, i):
            i += 1
        m += 1

    return m


def _has_vowel(stem: str) -> bool:
    """Check if stem contains a vowel."""
    for i in range(len(stem)):
        if not _is_consonant(stem, i):
            return True
    return False


def _ends_double_consonant(word: str) -> bool:
    """Check for double consonant ending (e.g., -ll, -ss, -zz)."""
    if len(word) < 2:
        return False
    return word[-1] == word[-2] and _is_consonant(word, len(word) - 1)


def _ends_cvc(word: str) -> bool:
    """
    Check for consonant-vowel-consonant ending where last consonant is not w, x, or y.
    """
    if len(word) < 3:
        return False
    return (_is_consonant(word, len(word) - 1) and
            not _is_consonant(word, len(word) - 2) and
            _is_consonant(word, len(word) - 3) and
            word[-1] not in 'wxy')


def _replace_suffix(word: str, suffix: str, replacement: str, min_measure: int = 0) -> str:
    """Replace suffix if word ends with it and measure condition is met."""
    if word.endswith(suffix):
        stem = word[:-len(suffix)]
        if _measure(stem) > min_measure:
            return stem + replacement
    return word


@lru_cache(maxsize=10000)
def porter_stem(word: str) -> str:
    """
    Porter Stemmer - 5-step suffix stripping algorithm.
    Based on Martin Porter's 1980 paper.

    Memoized with LRU cache for 50-70% speedup on repeated terms.
    """
    word = normalize_word(word)

    if len(word) <= 2:
        return word

    # Step 1a: Plurals
    if word.endswith('sses'):
        word = word[:-2]
    elif word.endswith('ies'):
        word = word[:-2]
    elif word.endswith('ss'):
        pass  # Keep ss
    elif word.endswith('s'):
        word = word[:-1]

    # Step 1b: Past tense and progressive
    flag = False
    if word.endswith('eed'):
        stem = word[:-3]
        if _measure(stem) > 0:
            word = word[:-1]  # eed -> ee
    elif word.endswith('ed'):
        stem = word[:-2]
        if _has_vowel(stem):
            word = stem
            flag = True
    elif word.endswith('ing'):
        stem = word[:-3]
        if _has_vowel(stem):
            word = stem
            flag = True

    if flag:
        if word.endswith('at') or word.endswith('bl') or word.endswith('iz'):
            word = word + 'e'
        elif _ends_double_consonant(word) and word[-1] not in 'lsz':
            word = word[:-1]
        elif _measure(word) == 1 and _ends_cvc(word):
            word = word + 'e'

    # Step 1c: Y to I
    if word.endswith('y'):
        stem = word[:-1]
        if _has_vowel(stem):
            word = stem + 'i'

    # Step 2: Double suffixes
    step2_suffixes = [
        ('ational', 'ate'), ('tional', 'tion'), ('enci', 'ence'), ('anci', 'ance'),
        ('izer', 'ize'), ('abli', 'able'), ('alli', 'al'), ('entli', 'ent'),
        ('eli', 'e'), ('ousli', 'ous'), ('ization', 'ize'), ('ation', 'ate'),
        ('ator', 'ate'), ('alism', 'al'), ('iveness', 'ive'), ('fulness', 'ful'),
        ('ousness', 'ous'), ('aliti', 'al'), ('iviti', 'ive'), ('biliti', 'ble'),
    ]
    for suffix, replacement in step2_suffixes:
        if word.endswith(suffix):
            stem = word[:-len(suffix)]
            if _measure(stem) > 0:
                word = stem + replacement
            break

    # Step 3: Derivational suffixes
    step3_suffixes = [
        ('icate', 'ic'), ('ative', ''), ('alize', 'al'), ('iciti', 'ic'),
        ('ical', 'ic'), ('ful', ''), ('ness', ''),
    ]
    for suffix, replacement in step3_suffixes:
        if word.endswith(suffix):
            stem = word[:-len(suffix)]
            if _measure(stem) > 0:
                word = stem + replacement
            break

    # Step 4: Remove suffixes
    step4_suffixes = [
        'al', 'ance', 'ence', 'er', 'ic', 'able', 'ible', 'ant', 'ement',
        'ment', 'ent', 'ion', 'ou', 'ism', 'ate', 'iti', 'ous', 'ive', 'ize',
    ]
    for suffix in step4_suffixes:
        if word.endswith(suffix):
            stem = word[:-len(suffix)]
            if _measure(stem) > 1:
                # Special case for -ion: stem must end in s or t
                if suffix == 'ion' and stem and stem[-1] not in 'st':
                    continue
                word = stem
            break

    # Step 5a: Remove final -e
    if word.endswith('e'):
        stem = word[:-1]
        m = _measure(stem)
        if m > 1 or (m == 1 and not _ends_cvc(stem)):
            word = stem

    # Step 5b: Reduce -ll to -l
    if word.endswith('ll') and _measure(word[:-1]) > 1:
        word = word[:-1]

    return word


def simple_stem(word: str) -> str:
    """Backward-compatible wrapper using Porter Stemmer."""
    return porter_stem(normalize_word(word))


def fuzzy_match(query_term: str, target: str) -> float:
    """Calculate similarity between two strings (0-1)."""
    query_term = normalize_word(query_term)
    target = normalize_word(target)

    if not query_term or not target:
        return 0.0

    # Exact match
    if query_term == target:
        return 1.0

    # Substring match
    if query_term in target:
        return 0.8
    if target in query_term:
        return 0.6

    # Stem match
    if simple_stem(query_term) == simple_stem(target):
        return 0.7

    # Prefix match (at least 3 chars)
    min_len = min(len(query_term), len(target))
    if min_len >= 3:
        prefix_len = 0
        for i in range(min_len):
            if query_term[i] == target[i]:
                prefix_len += 1
            else:
                break
        if prefix_len >= 3:
            return 0.4 * (prefix_len / min_len)

    return 0.0


def parse_frontmatter(content: str) -> Tuple[Dict, str]:
    """Extract YAML frontmatter and content from markdown."""
    frontmatter = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2].strip()

            # Simple YAML parsing (no external deps)
            for line in fm_text.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    # Handle arrays [item1, item2]
                    if value.startswith("[") and value.endswith("]"):
                        items = value[1:-1].split(",")
                        value = [item.strip().strip("'\"") for item in items]

                    frontmatter[key] = value

    return frontmatter, body


def extract_keywords(content: str, frontmatter: Dict) -> List[str]:
    """Extract searchable keywords from content."""
    keywords = set()

    # Add tags (high priority) - filter to strings only
    tags = frontmatter.get("tags", [])
    if isinstance(tags, list):
        keywords.update(t for t in tags if isinstance(t, str))
    elif isinstance(tags, str):
        keywords.add(tags)

    # Add title words
    title = frontmatter.get("title", "")
    if title and isinstance(title, str):
        for word in title.split():
            normalized = normalize_word(word)
            if normalized and normalized not in STOPWORDS and len(normalized) > 2:
                keywords.add(normalized)

    # Add category parts
    category = frontmatter.get("category", "")
    if category and isinstance(category, str):
        for part in category.replace("/", " ").replace("-", " ").split():
            normalized = normalize_word(part)
            if normalized and normalized not in STOPWORDS:
                keywords.add(normalized)

    # Extract headings
    headings = re.findall(r"^#+\s+(.+)$", content, re.MULTILINE)
    for heading in headings:
        for word in heading.split():
            normalized = normalize_word(word)
            if normalized and normalized not in STOPWORDS and len(normalized) > 2:
                keywords.add(normalized)

    # Extract code block languages
    code_langs = re.findall(r"```(\w+)", content)
    keywords.update(code_langs)

    # Extract important terms (capitalized words, technical terms)
    technical_terms = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', content)  # CamelCase
    for term in technical_terms:
        keywords.add(term.lower())

    return list(keywords)


def extract_bigrams(content: str, frontmatter: Dict) -> List[str]:
    """
    Extract 2-word phrases (bigrams) from titles and headings.
    Returns hyphenated bigrams like 'error-handling', 'api-reference'.
    """
    bigrams: Set[str] = set()

    # Extract from title
    title = frontmatter.get("title", "")
    if title and isinstance(title, str):
        title_words = []
        for word in title.split():
            normalized = normalize_word(word)
            if normalized and normalized not in STOPWORDS and len(normalized) > 1:
                title_words.append(porter_stem(normalized))

        for i in range(len(title_words) - 1):
            bigram = f"{title_words[i]}-{title_words[i+1]}"
            bigrams.add(bigram)

    # Extract from headings
    headings = re.findall(r"^#+\s+(.+)$", content, re.MULTILINE)
    for heading in headings:
        heading_words = []
        for word in heading.split():
            normalized = normalize_word(word)
            if normalized and normalized not in STOPWORDS and len(normalized) > 1:
                heading_words.append(porter_stem(normalized))

        for i in range(len(heading_words) - 1):
            bigram = f"{heading_words[i]}-{heading_words[i+1]}"
            bigrams.add(bigram)

    return list(bigrams)


def write_index_safely(index_path: Path, data: Dict) -> None:
    """
    Write index atomically via temp-file + os.replace().

    v3.0.1: the previous fcntl-based version opened the destination in
    ``'w'`` mode (truncating the file) *before* acquiring the exclusive
    lock, so two concurrent writers could both truncate. Atomic rename
    fixes the race and is portable across POSIX and Windows, removing
    the fcntl dependency that prevented Windows support.
    """
    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = index_path.with_suffix(index_path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(str(tmp), str(index_path))


def knowledge_dirs() -> List[Path]:
    """Return BloxCue-owned knowledge dirs plus readable legacy dirs."""
    dirs = [MEMORY_DIR]
    legacy = LEGACY_MEMORY_DIR
    try:
        if legacy.expanduser().resolve() != MEMORY_DIR.expanduser().resolve() and legacy.exists():
            dirs.append(legacy)
    except Exception:
        if legacy.exists():
            dirs.append(legacy)
    return dirs


def _entry_path_for(filepath: Path, base_dir: Path) -> str:
    rel_path = str(filepath.relative_to(base_dir))
    if base_dir == LEGACY_MEMORY_DIR and MEMORY_DIR != LEGACY_MEMORY_DIR:
        return f"legacy://claude-memory/{rel_path}"
    return rel_path


def _resolve_entry_path(path: str) -> Optional[Path]:
    if path.startswith("legacy://claude-memory/"):
        return LEGACY_MEMORY_DIR / path.replace("legacy://claude-memory/", "", 1)
    return MEMORY_DIR / path


def ensure_learnings_db() -> None:
    """Create the BloxCue-owned SQLite learnings database if needed."""
    LEARNINGS_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(LEARNINGS_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                title TEXT,
                tags TEXT NOT NULL DEFAULT '[]',
                source TEXT NOT NULL DEFAULT 'local',
                legacy_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def add_learning(content: str, title: str = "", tags: Optional[List[str]] = None,
                 source: str = "local", legacy_path: str = "") -> int:
    """Add a learned memory record to SQLite and return its integer id."""
    if not content or not content.strip():
        raise ValueError("learning content is required")
    ensure_learnings_db()
    now = datetime.now().isoformat()
    tag_list = tags if isinstance(tags, list) else []
    with sqlite3.connect(LEARNINGS_DB) as conn:
        cur = conn.execute(
            """
            INSERT INTO learnings (content, title, tags, source, legacy_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (content.strip(), title.strip(), json.dumps(tag_list), source, legacy_path, now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def iter_learnings() -> Iterable[Dict]:
    """Yield local SQLite learned memory rows."""
    if not LEARNINGS_DB.exists():
        return []
    ensure_learnings_db()
    with sqlite3.connect(LEARNINGS_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, content, title, tags, source, legacy_path, created_at, updated_at FROM learnings ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def learning_row_to_entry(row: Dict) -> Optional[Dict]:
    content = row.get("content", "")
    if not content:
        return None
    try:
        tags = json.loads(row.get("tags") or "[]")
        if not isinstance(tags, list):
            tags = []
    except json.JSONDecodeError:
        tags = []
    title = row.get("title") or f"Learning {row.get('id')}"
    frontmatter = {"title": title, "category": "learnings", "tags": tags}
    return {
        "path": f"memory://learning/{row.get('id')}",
        "title": title,
        "category": "learnings",
        "tags": tags,
        "keywords": extract_keywords(content, frontmatter),
        "bigrams": extract_bigrams(content, frontmatter),
        "size": len(content),
        "modified": row.get("updated_at") or row.get("created_at") or "",
        "preview": content[:300].replace("\n", " ").strip(),
        "source": "sqlite",
        "legacy_path": row.get("legacy_path") or "",
    }


def get_learning_content(learning_id: str) -> str:
    if not learning_id:
        return ""
    if not LEARNINGS_DB.exists():
        return ""
    ensure_learnings_db()
    with sqlite3.connect(LEARNINGS_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, content, title, tags, source, legacy_path, created_at, updated_at FROM learnings WHERE id = ?",
            (learning_id,),
        ).fetchone()
    if not row:
        return ""
    data = dict(row)
    lines = []
    if data.get("title"):
        lines.append(f"Title: {data['title']}")
    if data.get("tags"):
        try:
            tags = json.loads(data["tags"])
            if tags:
                lines.append("Tags: " + ", ".join(str(t) for t in tags))
        except json.JSONDecodeError:
            pass
    if data.get("legacy_path"):
        lines.append(f"Imported from: {data['legacy_path']}")
    lines.append(f"Updated: {data.get('updated_at', 'unknown')}")
    lines.append("---")
    lines.append(data.get("content", ""))
    return "\n".join(lines)


def index_file(filepath: Path, base_dir: Optional[Path] = None) -> Optional[Dict]:
    """Index a single markdown file.

    Security (v3.0.1): resolve the real path and reject anything that lands
    outside an allowed knowledge root. This prevents a symlink inside
    MEMORY_DIR (e.g. ~/.bloxcue/knowledge/leak.md -> /etc/passwd) from
    leaking external file content into index previews. Symlinks pointing
    at files inside the memory dirs remain legitimate and are allowed.
    """
    try:
        # Resolve symlinks before deciding whether the file is in scope.
        try:
            resolved = filepath.resolve()
        except (OSError, RuntimeError):
            return None

        allowed_roots = []
        for d in knowledge_dirs():
            try:
                allowed_roots.append(d.resolve())
            except (OSError, RuntimeError):
                continue

        # Use the os.sep suffix trick (mirrors get_file_content) so a
        # sibling like /a/.bloxcue-evil cannot satisfy a /a/.bloxcue base.
        in_allowed = any(
            str(resolved) == str(root) or str(resolved).startswith(str(root) + os.sep)
            for root in allowed_roots
        )
        if not in_allowed:
            print(
                f"Skipping symlink outside memory root: {filepath}",
                file=sys.stderr,
            )
            return None

        content = filepath.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(content)

        root = base_dir or MEMORY_DIR
        relative_path = _entry_path_for(filepath, root)
        stat = filepath.stat()

        return {
            "path": str(relative_path),
            "title": frontmatter.get("title", filepath.stem.replace("-", " ").replace("_", " ").title()),
            "category": frontmatter.get("category", str(filepath.relative_to(root).parent)),
            "tags": frontmatter.get("tags", []),
            "keywords": extract_keywords(body, frontmatter),
            "bigrams": extract_bigrams(body, frontmatter),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "preview": body[:300].replace("\n", " ").strip(),
        }
    except Exception as e:
        print(f"Error indexing {filepath}: {e}", file=sys.stderr)
        return None


def build_index(single_file: Optional[Path] = None) -> Dict:
    """Build index of all markdown files or update single file."""

    # Load existing index if updating single file
    if single_file and INDEX_FILE.exists():
        try:
            index = json.loads(INDEX_FILE.read_text())
            # Remove existing entry for this file
            rel_path = str(single_file.relative_to(MEMORY_DIR))
            index["files"] = [f for f in index["files"] if f["path"] != rel_path]
        except Exception:
            index = {"files": [], "built": datetime.now().isoformat()}
    else:
        index = {"files": [], "built": datetime.now().isoformat()}

    # Determine files to index. New installs use ~/.bloxcue/knowledge; existing
    # ~/.claude-memory users remain readable without moving files.
    scan_roots = [MEMORY_DIR]
    if not single_file:
        scan_roots = knowledge_dirs()

    for root in scan_roots:
        if single_file:
            md_files = [single_file] if single_file.exists() else []
        elif root.exists():
            md_files = list(root.rglob("*.md"))
        else:
            md_files = []

        for filepath in md_files:
            # Skip hidden files and scripts directory
            relative_parts = filepath.relative_to(root).parts
            if any(part.startswith(".") for part in relative_parts):
                continue
            if "scripts" in relative_parts:
                continue

            entry = index_file(filepath, root)
            if entry:
                index["files"].append(entry)
                print(f"Indexed: {entry['path']}")

    # Merge BloxCue-owned SQLite learnings.
    sqlite_count = 0
    for row in iter_learnings():
        entry = learning_row_to_entry(row)
        if entry and not any(f.get("path") == entry["path"] for f in index["files"]):
            index["files"].append(entry)
            sqlite_count += 1
    if sqlite_count > 0:
        print(f"Merged {sqlite_count} SQLite learnings", file=sys.stderr)

    # Merge PostgreSQL learnings (if available)
    if HAS_PG_PROVIDER and PG_ENABLED and pg_is_available(PG_DATABASE_URL):
        try:
            pg_learnings = pg_fetch_learnings(PG_DATABASE_URL, limit=500)
            pg_count = 0
            for learning in pg_learnings:
                entry = pg_learning_to_entry(learning, extract_keywords_fn=extract_keywords)
                if entry and not any(f.get("path") == entry["path"] for f in index["files"]):
                    index["files"].append(entry)
                    pg_count += 1
            if pg_count > 0:
                print(f"Merged {pg_count} PostgreSQL learnings", file=sys.stderr)
            index["pg_fetched_at"] = datetime.now().isoformat()
        except Exception as e:
            print(f"[BloxCue PG] Error merging learnings: {e}", file=sys.stderr)

    index["built"] = datetime.now().isoformat()

    # Calculate IDF scores and document stats for BM25
    index["idf"] = calculate_idf(index)
    index["doc_stats"] = calculate_doc_stats(index)

    # Save index with file locking for concurrent safety
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_index_safely(INDEX_FILE, index)

    # Invalidate cache so next load picks up changes
    global _index_cache, _index_mtime
    _index_cache = None
    _index_mtime = None

    return index


def calculate_idf(index: Dict) -> Dict[str, float]:
    """
    Calculate IDF (Inverse Document Frequency) for all terms across documents.
    IDF formula: log(N / (1 + df)) where N = total docs, df = docs containing term
    """
    import math

    term_doc_count: Dict[str, int] = {}  # term -> number of docs containing it
    total_docs = len(index.get("files", []))

    if total_docs == 0:
        return {}

    for entry in index.get("files", []):
        # Collect unique stemmed terms from this doc
        doc_terms: Set[str] = set()

        # From title
        title = entry.get("title", "")
        if isinstance(title, str):
            for word in title.lower().split():
                normalized = normalize_word(word)
                if normalized and normalized not in STOPWORDS:
                    doc_terms.add(porter_stem(normalized))

        # From tags
        tags = entry.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str):
                    doc_terms.add(porter_stem(normalize_word(tag)))

        # From keywords
        keywords = entry.get("keywords", [])
        if isinstance(keywords, list):
            for keyword in keywords:
                if isinstance(keyword, str):
                    doc_terms.add(porter_stem(normalize_word(keyword)))

        # Count term occurrences across docs
        for term in doc_terms:
            if term:
                term_doc_count[term] = term_doc_count.get(term, 0) + 1

    # Calculate IDF: log((N + 1) / (df + 1)) - ensures non-negative values
    idf: Dict[str, float] = {}
    for term, df in term_doc_count.items():
        idf[term] = max(0.0, math.log((total_docs + 1) / (df + 1)))

    return idf


def calculate_doc_stats(index: Dict) -> Dict:
    """
    Calculate per-document term frequencies and lengths for BM25 scoring.
    Stores term frequency counts and total term count per document.

    Returns:
        {
            "avg_dl": float,  # average document length across all docs
            "docs": {
                "path": {
                    "tf": {"stemmed_term": count, ...},
                    "dl": int  # total terms in document
                }
            }
        }
    """
    docs_stats: Dict[str, Dict] = {}
    total_length = 0

    for entry in index.get("files", []):
        path = entry.get("path", "")
        term_freq: Dict[str, int] = {}

        def count_term(term: str, weight: int = 1):
            if term:
                term_freq[term] = term_freq.get(term, 0) + weight

        # Title terms (weight 3 - most important)
        title = entry.get("title", "")
        if isinstance(title, str):
            for word in title.lower().split():
                stemmed = porter_stem(normalize_word(word))
                if stemmed and stemmed not in STOPWORDS:
                    count_term(stemmed, 3)

        # Tags (weight 2)
        tags = entry.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str):
                    stemmed = porter_stem(normalize_word(tag))
                    if stemmed:
                        count_term(stemmed, 2)

        # Keywords (weight 1)
        keywords = entry.get("keywords", [])
        if isinstance(keywords, list):
            for kw in keywords:
                if isinstance(kw, str):
                    stemmed = porter_stem(normalize_word(kw))
                    if stemmed:
                        count_term(stemmed, 1)

        # Category (weight 1)
        category = entry.get("category", "")
        if isinstance(category, str):
            for part in category.replace("/", " ").replace("-", " ").split():
                stemmed = porter_stem(normalize_word(part))
                if stemmed and stemmed not in STOPWORDS:
                    count_term(stemmed, 1)

        # Preview (weight 1 per unique term)
        preview = entry.get("preview", "")
        if isinstance(preview, str):
            seen_preview: Set[str] = set()
            for word in preview.lower().split():
                stemmed = porter_stem(normalize_word(word))
                if stemmed and stemmed not in STOPWORDS and stemmed not in seen_preview:
                    count_term(stemmed, 1)
                    seen_preview.add(stemmed)

        dl = sum(term_freq.values())
        total_length += dl

        docs_stats[path] = {
            "tf": term_freq,
            "dl": dl
        }

    total_docs = len(index.get("files", []))
    avg_dl = total_length / total_docs if total_docs > 0 else 1.0

    return {
        "avg_dl": avg_dl,
        "docs": docs_stats
    }


# Index cache for avoiding repeated disk reads
_index_cache: Optional[Dict] = None
_index_mtime: Optional[float] = None


def load_index() -> Dict:
    """
    Load existing index with caching.

    Uses mtime checking to invalidate cache when index file changes.
    Eliminates repeated JSON parsing overhead (~28KB per search).
    """
    global _index_cache, _index_mtime

    if INDEX_FILE.exists():
        try:
            current_mtime = INDEX_FILE.stat().st_mtime

            # Return cached index if file hasn't changed
            if _index_cache is not None and _index_mtime == current_mtime:
                # Check PG cache TTL - rebuild if PG data is stale
                if HAS_PG_PROVIDER and PG_ENABLED:
                    pg_fetched = _index_cache.get("pg_fetched_at")
                    if pg_fetched:
                        try:
                            fetched_time = datetime.fromisoformat(pg_fetched)
                            age_seconds = (datetime.now() - fetched_time).total_seconds()
                            if age_seconds > PG_CACHE_TTL:
                                # PG data stale, trigger rebuild
                                _index_cache = None
                                _index_mtime = None
                                return build_index()
                        except (ValueError, TypeError):
                            pass
                return _index_cache

            # Load and cache
            _index_cache = json.loads(INDEX_FILE.read_text())
            _index_mtime = current_mtime
            return _index_cache
        except Exception:
            pass

    return build_index()


def log_usage(query: str, results: List[Dict]):
    """
    Append a search usage record to the usage log (JSONL format).
    Tracks queries, results, scores, and whether results were found.
    """
    record = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "results": [r["entry"]["path"] for r in results[:5]],
        "scores": [round(r["score"], 2) for r in results[:5]],
        "hit": len(results) > 0,
    }
    try:
        with open(USAGE_FILE, "a") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception:
        pass  # Non-critical - don't break search on logging failure


def load_usage_log() -> List[Dict]:
    """Load all usage records from the JSONL log file."""
    records = []
    if not USAGE_FILE.exists():
        return records
    try:
        for line in USAGE_FILE.read_text().strip().split("\n"):
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # Skip corrupt lines, keep parsing
    except Exception:
        pass
    return records


def bm25_score(term: str, doc_path: str, doc_stats: Dict, idf_scores: Dict,
               k1: float = 1.5, b: float = 0.75) -> float:
    """
    Calculate BM25 score for a single term against a single document.

    BM25 formula: IDF(q) * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl/avgdl))

    Args:
        term: Stemmed query term
        doc_path: Document path (key into doc_stats)
        doc_stats: Pre-computed document statistics from calculate_doc_stats()
        idf_scores: Pre-computed IDF scores
        k1: Term frequency saturation parameter (1.5 = standard)
        b: Length normalization parameter (0.75 = standard)

    Returns:
        BM25 score for this term-document pair
    """
    idf = idf_scores.get(term, 0.0)
    if idf == 0:
        return 0.0

    doc = doc_stats.get("docs", {}).get(doc_path, {})
    tf = doc.get("tf", {}).get(term, 0)
    if tf == 0:
        return 0.0

    dl = doc.get("dl", 1)
    avg_dl = doc_stats.get("avg_dl", 1.0) or 1.0  # Guard against zero

    numerator = tf * (k1 + 1)
    denominator = tf + k1 * (1 - b + b * (dl / avg_dl))

    return idf * (numerator / denominator)


def search(query: str, limit: int = 5) -> List[Dict]:
    """
    Search indexed files using BM25 scoring with query expansion,
    bigram matching, intent detection, recency boosting, and MMR diversity.
    """
    if not isinstance(query, str) or not query.strip():
        return []

    index = load_index()
    idf_scores = index.get("idf", {})
    doc_stats = index.get("doc_stats", {})

    # Detect query intent
    intent, weight_adjustments = detect_query_intent(query)

    # Parse query terms
    query_terms = []
    for word in query.lower().split():
        normalized = normalize_word(word)
        if normalized and len(normalized) > 1:
            if normalized not in STOPWORDS or len(query.split()) <= 2:
                query_terms.append(normalized)

    if not query_terms:
        query_terms = [normalize_word(w) for w in query.lower().split() if normalize_word(w)]

    # Expand query with synonyms: returns [(term, weight), ...]
    expanded = expand_query(query_terms)

    # Build weighted term map (stemmed), keeping highest weight per term
    term_weights: Dict[str, float] = {}
    for term, weight in expanded:
        stemmed = porter_stem(term)
        if stemmed and stemmed not in STOPWORDS:
            term_weights[stemmed] = max(term_weights.get(stemmed, 0), weight)

    # Extract bigrams from query
    query_bigrams = []
    normalized_words = [normalize_word(w) for w in query.lower().split()
                        if normalize_word(w) not in STOPWORDS and len(normalize_word(w)) > 1]
    for i in range(len(normalized_words) - 1):
        query_bigrams.append(f"{porter_stem(normalized_words[i])}-{porter_stem(normalized_words[i+1])}")

    results = []

    for entry in index.get("files", []):
        path = entry.get("path", "")
        score = 0.0

        # BM25 scoring across all weighted terms
        for term, weight in term_weights.items():
            score += bm25_score(term, path, doc_stats, idf_scores) * weight

        # Bigram bonus (phrase matching)
        entry_bigrams = entry.get("bigrams", [])
        for qbigram in query_bigrams:
            for ebigram in entry_bigrams:
                if qbigram == ebigram:
                    score += 5.0
                elif qbigram in ebigram or ebigram in qbigram:
                    score += 2.5

        # Fuzzy fallback: catch matches that BM25 missed (typos, partial matches)
        if score == 0:
            title = entry.get("title", "").lower()
            for term in query_terms:
                match_score = fuzzy_match(term, title)
                if match_score > 0.5:
                    score += match_score * 3.0

            tags = entry.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, str):
                        for term in query_terms:
                            match_score = fuzzy_match(term, tag)
                            if match_score > 0.5:
                                score += match_score * 2.0

        # Intent-based boost
        if intent != "general" and score > 0:
            for field, multiplier in weight_adjustments.items():
                if field == "title":
                    title_lower = entry.get("title", "").lower()
                    title_stems = {porter_stem(normalize_word(w)) for w in title_lower.split()}
                    for term in query_terms:
                        if porter_stem(term) in title_stems:
                            score *= multiplier
                            break
                elif field == "tags":
                    tags = entry.get("tags", [])
                    if isinstance(tags, list):
                        tag_stems = {porter_stem(normalize_word(t)) for t in tags if isinstance(t, str)}
                        for term in query_terms:
                            if porter_stem(term) in tag_stems:
                                score *= multiplier
                                break
                elif field == "preview":
                    preview = entry.get("preview", "").lower()
                    for term in query_terms:
                        if term in preview:
                            score *= min(multiplier, 1.5)
                            break

        if score > 0:
            results.append({"entry": entry, "score": score})

    # Recency boost: gently favor recently modified blocks
    for result in results:
        modified = result["entry"].get("modified", "")
        try:
            mod_date = datetime.fromisoformat(modified)
            age_days = (datetime.now() - mod_date).days
            # ~10% boost for fresh docs, decays over 30 days
            recency_factor = 1.0 + 0.1 / (1.0 + age_days / 30.0)
            result["score"] *= recency_factor
        except (ValueError, TypeError):
            pass

    # Re-sort after recency
    results.sort(key=lambda x: x["score"], reverse=True)

    # MMR diversity: reduce redundancy in top results
    if len(results) > 1:
        selected = [results[0]]
        remaining = results[1:]

        while remaining and len(selected) < limit:
            best_idx = 0
            best_mmr = -float("inf")

            for i, candidate in enumerate(remaining):
                cand_terms = set(candidate["entry"].get("keywords", []))
                max_overlap = 0.0
                for sel in selected:
                    sel_terms = set(sel["entry"].get("keywords", []))
                    if cand_terms and sel_terms:
                        union = len(cand_terms | sel_terms)
                        if union > 0:
                            max_overlap = max(max_overlap,
                                              len(cand_terms & sel_terms) / union)

                # MMR: 0.7 * relevance - 0.3 * redundancy_penalty
                mmr = 0.7 * candidate["score"] - 0.3 * max_overlap * candidate["score"]

                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        results = selected

    final = results[:limit]

    # Log usage for health tracking
    log_usage(query, final)

    return final


def display_results(results: List[Dict], verbose: bool = False):
    """Display search results."""
    if not results:
        print("No results found.")
        return

    for i, result in enumerate(results, 1):
        entry = result["entry"]
        score = result["score"]
        is_pg = entry.get("path", "").startswith("pg://")

        print(f"\n{i}. {entry['title']}")
        print(f"   Path: {entry['path']}")
        print(f"   Category: {entry['category']}")
        if entry.get("tags"):
            tags = entry['tags']
            if isinstance(tags, list):
                tags_str = ', '.join(str(t) for t in tags if t is not None)
            else:
                tags_str = str(tags) if tags else ""
            if tags_str:
                print(f"   Tags: {tags_str}")

        if verbose:
            print(f"   Score: {score:.1f}")
            if is_pg:
                print(f"   Preview: {entry.get('preview', '')[:150]}...")
            else:
                filepath = MEMORY_DIR / entry["path"]
                if filepath.exists():
                    print(f"   Preview: {entry.get('preview', '')[:150]}...")


def list_files():
    """List all indexed files."""
    index = load_index()
    files = index.get("files", [])

    print(f"Indexed blocks: {len(files)}\n")

    if not files:
        print("No files indexed yet. Add some markdown files and run the indexer.")
        return

    # Group by category
    by_category = {}
    for entry in files:
        cat = entry.get("category", "uncategorized")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(entry)

    for category in sorted(by_category.keys()):
        print(f"{category}/")
        for entry in sorted(by_category[category], key=lambda x: x.get("title", "")):
            print(f"  • {entry['title']}")
    print()


def get_file_content(path: str) -> str:
    """Get full content of a file or learned memory for context injection."""
    if not isinstance(path, str):
        return ""

    if path.startswith("memory://learning/"):
        learning_id = path.replace("memory://learning/", "", 1)
        return get_learning_content(learning_id)

    # Route pg:// paths to PostgreSQL provider
    if path.startswith("pg://learning/"):
        learning_id = path.replace("pg://learning/", "")
        if HAS_PG_PROVIDER and PG_ENABLED:
            return pg_fetch_learning_content(PG_DATABASE_URL, learning_id)
        return ""

    filepath = _resolve_entry_path(path)
    if filepath is None:
        return ""

    # Security: Validate file is within MEMORY_DIR (prevent path traversal)
    try:
        resolved_path = filepath.resolve()
        allowed_roots = [d.resolve() for d in knowledge_dirs()]
        # M-1 fix: Use os.sep suffix to prevent prefix bypass
        # (e.g., /a/batch would falsely match /a/b without trailing separator)
        if not any(str(resolved_path) == str(root) or str(resolved_path).startswith(str(root) + os.sep)
                   for root in allowed_roots):
            return ""  # Path traversal attempt - reject silently
    except Exception:
        return ""

    if resolved_path.exists():
        content = resolved_path.read_text()
        _, body = parse_frontmatter(content)
        return body
    return ""


def generate_health_report() -> str:
    """
    Generate a comprehensive health report for knowledge blocks.

    Includes: freshness analysis, usage statistics, knowledge gaps,
    and actionable suggestions.
    """
    index = load_index()
    files = index.get("files", [])

    if not files:
        return "No blocks indexed. Nothing to report."

    now = datetime.now()
    fresh, aging, stale = [], [], []

    for entry in files:
        modified = entry.get("modified", "")
        try:
            mod_date = datetime.fromisoformat(modified)
            age_days = (now - mod_date).days
        except (ValueError, TypeError):
            age_days = 999

        entry_info = {
            "title": entry["title"],
            "path": entry["path"],
            "age_days": age_days,
        }

        if age_days < 30:
            fresh.append(entry_info)
        elif age_days < 90:
            aging.append(entry_info)
        else:
            stale.append(entry_info)

    total = len(files)
    lines = [
        "Block Health Report",
        "=" * 40,
        f"Total blocks: {total}",
        f"Fresh (< 30 days): {len(fresh)} ({100 * len(fresh) // total}%)",
        f"Aging (30-90 days): {len(aging)} ({100 * len(aging) // total}%)",
        f"Stale (> 90 days): {len(stale)} ({100 * len(stale) // total}%)",
        "",
    ]

    # Usage statistics
    usage = load_usage_log()
    if usage:
        # Most retrieved blocks
        retrieval_count: Dict[str, int] = {}
        for record in usage:
            for path in record.get("results", []):
                retrieval_count[path] = retrieval_count.get(path, 0) + 1

        if retrieval_count:
            sorted_retrievals = sorted(retrieval_count.items(), key=lambda x: -x[1])
            lines.append("Most Retrieved")
            lines.append("-" * 40)
            for path, count in sorted_retrievals[:5]:
                lines.append(f"  {path} ({count} retrievals)")
            lines.append("")

        # Never retrieved blocks
        all_paths = {entry["path"] for entry in files}
        retrieved_paths = set(retrieval_count.keys())
        never_retrieved = all_paths - retrieved_paths
        if never_retrieved:
            lines.append("Never Retrieved")
            lines.append("-" * 40)
            for path in sorted(never_retrieved):
                lines.append(f"  {path}")
            lines.append("")

        # Knowledge gaps: queries with no results
        missed_queries: Dict[str, int] = {}
        for record in usage:
            if not record.get("hit", True):
                q = record.get("query", "").lower().strip()
                if q:
                    missed_queries[q] = missed_queries.get(q, 0) + 1

        if missed_queries:
            sorted_gaps = sorted(missed_queries.items(), key=lambda x: -x[1])
            lines.append("Knowledge Gaps (unmatched queries)")
            lines.append("-" * 40)
            for query, count in sorted_gaps[:10]:
                lines.append(f"  \"{query}\" ({count} missed)")
            lines.append("")

        lines.append(f"Total searches logged: {len(usage)}")
        hit_count = sum(1 for r in usage if r.get("hit", False))
        if usage:
            lines.append(f"Hit rate: {100 * hit_count // len(usage)}%")
        lines.append("")

    # Stale blocks detail
    if stale:
        lines.append("Stale Blocks (consider updating)")
        lines.append("-" * 40)
        for s in sorted(stale, key=lambda x: -x["age_days"]):
            lines.append(f"  {s['title']} ({s['path']}) - {s['age_days']} days old")
        lines.append("")

    # IDF stats (distinctive terms)
    idf = index.get("idf", {})
    if idf:
        sorted_idf = sorted(idf.items(), key=lambda x: x[1], reverse=True)
        lines.append("Most Distinctive Terms (high IDF)")
        lines.append("-" * 40)
        for term, score in sorted_idf[:10]:
            lines.append(f"  {term}: {score:.2f}")
        lines.append("")

    # Suggestions
    suggestions = []
    if stale:
        oldest = max(stale, key=lambda x: x["age_days"])
        suggestions.append(f"Update: {oldest['path']} ({oldest['age_days']} days old)")
    if usage:
        missed = {q for q, c in missed_queries.items() if c >= 2} if missed_queries else set()
        for q in list(missed)[:3]:
            suggestions.append(f"Create block for: \"{q}\" ({missed_queries[q]} missed searches)")
    if usage and never_retrieved:
        nr_list = sorted(never_retrieved)
        if len(nr_list) > 2:
            suggestions.append(f"Review {len(nr_list)} never-retrieved blocks (may be outdated)")

    if suggestions:
        lines.append("Suggestions")
        lines.append("-" * 40)
        for s in suggestions:
            lines.append(f"  - {s}")
        lines.append("")

    return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    """Estimate token count for text. Roughly 1 token per 4 characters."""
    return len(text) // 4


def _keyword_overlap(entry_a: Dict, entry_b: Dict) -> float:
    """
    Calculate keyword overlap ratio between two index entries.
    Returns 0.0 (no overlap) to 1.0 (identical keywords).
    """
    kw_a = set(entry_a.get("keywords", []))
    kw_b = set(entry_b.get("keywords", []))
    if not kw_a or not kw_b:
        return 0.0
    union = len(kw_a | kw_b)
    if union == 0:
        return 0.0
    return len(kw_a & kw_b) / union


def inject_context(query: str, limit: int = 5, max_tokens: Optional[int] = None) -> str:
    """
    Search and inject context with token budget awareness, deduplication,
    and priority-based content selection.

    Returns formatted text ready for LLM context injection, including:
    - Metadata header (block count, token usage, query)
    - Full content for top blocks (within budget)
    - Summaries for lower-ranked blocks that don't fit
    - Title+tags references for the rest

    Args:
        query: Search query
        limit: Max number of blocks to consider
        max_tokens: Token budget (default: MAX_INJECT_TOKENS)
    """
    if max_tokens is None:
        max_tokens = MAX_INJECT_TOKENS

    results = search(query, limit=limit)
    if not results:
        return f"[BloxCue: No blocks found for: \"{query}\"]"

    # Deduplicate: skip blocks with >60% keyword overlap with already-selected
    deduped = [results[0]]
    for result in results[1:]:
        dominated = False
        for selected in deduped:
            if _keyword_overlap(result["entry"], selected["entry"]) > 0.6:
                dominated = True
                break
        if not dominated:
            deduped.append(result)

    # Build injection with token budget
    blocks_output = []
    tokens_used = 0
    block_num = 0
    summary_token_limit = 75  # ~300 chars / 4

    for result in deduped:
        entry = result["entry"]
        score = result["score"]
        path = entry["path"]
        title = entry.get("title", path)
        tags = entry.get("tags", [])
        tags_str = ", ".join(str(t) for t in tags if t) if isinstance(tags, list) else ""
        modified = entry.get("modified", "unknown")

        # Try to get age in days
        age_str = "unknown"
        try:
            mod_date = datetime.fromisoformat(modified)
            age_days = (datetime.now() - mod_date).days
            if age_days == 0:
                age_str = "today"
            elif age_days == 1:
                age_str = "1 day ago"
            else:
                age_str = f"{age_days} days ago"
        except (ValueError, TypeError):
            pass

        block_num += 1

        # Get full content
        content = get_file_content(path)
        content_tokens = estimate_tokens(content) if content else 0

        # Header for this block
        header = f"### Block {block_num}: {title} (score: {score:.1f}, updated: {age_str})"
        if tags_str:
            header += f"\nTags: {tags_str}"
        header_tokens = estimate_tokens(header)

        remaining = max_tokens - tokens_used

        if remaining <= header_tokens + 10:
            # No room even for a reference - stop
            break

        if content and content_tokens + header_tokens <= remaining:
            # Full content fits
            block_text = f"{header}\n\n{content}"
            tokens_used += estimate_tokens(block_text)
            blocks_output.append(block_text)

        elif content and header_tokens + summary_token_limit <= remaining:
            # Summary fits
            summary = content[:300].rstrip()
            if len(content) > 300:
                summary += "..."
            block_text = f"{header}\n[Summary - full block at: {path}]\n\n{summary}"
            tokens_used += estimate_tokens(block_text)
            blocks_output.append(block_text)

        else:
            # Reference only
            ref = f"{header}\n[Reference only - retrieve full block with: get_block(\"{path}\")]"
            tokens_used += estimate_tokens(ref)
            blocks_output.append(ref)

    # Build metadata header
    meta = f"[BloxCue: Injected {len(blocks_output)} block(s), ~{tokens_used} tokens, query: \"{query}\"]"

    parts = [meta, "---"]
    parts.extend(blocks_output)

    return "\n\n".join(parts)


def import_postgres_learnings(url: str, limit: int = 500) -> int:
    """Import legacy Continuous-Claude archival_memory rows into SQLite."""
    if not HAS_PG_PROVIDER:
        raise RuntimeError("pg_provider is unavailable")
    if not url:
        raise ValueError("PostgreSQL URL is required")
    if not pg_is_available(url):
        raise RuntimeError("PostgreSQL is not reachable")

    count = 0
    for learning in pg_fetch_learnings(url, limit=limit):
        content = learning.get("content", "")
        metadata = learning.get("metadata", {}) if isinstance(learning.get("metadata"), dict) else {}
        learning_type = metadata.get("learning_type", "learning")
        context = metadata.get("context", "")
        title = learning_type.replace("_", " ").title()
        if context:
            title = f"{title}: {context[:80]}"
        tags = metadata.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        legacy_path = f"pg://learning/{learning.get('id', '')}"
        add_learning(content, title=title, tags=tags, source="postgres-import", legacy_path=legacy_path)
        count += 1
    return count


def display_learning_rows(rows: Iterable[Dict]) -> None:
    rows = list(rows)
    if not rows:
        print("No learned memory records.")
        return
    for row in rows:
        try:
            tags = json.loads(row.get("tags") or "[]")
        except json.JSONDecodeError:
            tags = []
        tags_str = f" [{', '.join(str(t) for t in tags)}]" if tags else ""
        title = row.get("title") or f"Learning {row.get('id')}"
        print(f"{row.get('id')}. {title}{tags_str}")


def main():
    parser = argparse.ArgumentParser(
        description="bloxcue Indexer - Index and search context blocks"
    )
    parser.add_argument(
        "--search", "-s", type=str, help="Search query"
    )
    parser.add_argument(
        "--list", "-l", action="store_true", help="List all indexed files"
    )
    parser.add_argument(
        "--rebuild", "-r", action="store_true", help="Force rebuild index"
    )
    parser.add_argument(
        "--file", "-f", type=str, help="Index single file"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show more details"
    )
    parser.add_argument(
        "--limit", "-n", type=int, default=5, help="Max results (default: 5)"
    )
    parser.add_argument(
        "--health", action="store_true", help="Show block health report"
    )
    parser.add_argument(
        "--json", "-j", action="store_true", help="Output as JSON"
    )
    parser.add_argument(
        "--add-learning", type=str, help="Add a learned memory record to SQLite"
    )
    parser.add_argument(
        "--learning-title", type=str, default="", help="Title for --add-learning"
    )
    parser.add_argument(
        "--learning-tags", type=str, default="", help="Comma-separated tags for --add-learning"
    )
    parser.add_argument(
        "--list-learnings", action="store_true", help="List SQLite learned memory records"
    )
    parser.add_argument(
        "--import-postgres", type=str, nargs="?", const=PG_DATABASE_URL,
        help="Import legacy Continuous-Claude archival_memory rows from PostgreSQL into SQLite"
    )
    parser.add_argument(
        "--import-limit", type=int, default=500, help="Max rows for --import-postgres"
    )

    args = parser.parse_args()

    if args.add_learning:
        tags = [t.strip() for t in args.learning_tags.split(",") if t.strip()]
        learning_id = add_learning(args.add_learning, title=args.learning_title, tags=tags)
        print(f"Added learning: memory://learning/{learning_id}")

    elif args.list_learnings:
        if args.json:
            print(json.dumps(list(iter_learnings()), indent=2))
        else:
            display_learning_rows(iter_learnings())

    elif args.import_postgres is not None:
        imported = import_postgres_learnings(args.import_postgres, limit=args.import_limit)
        print(f"Imported {imported} learning(s) into {LEARNINGS_DB}")

    elif args.health:
        print(generate_health_report())

    elif args.file:
        filepath = Path(args.file)
        if not filepath.is_absolute():
            filepath = MEMORY_DIR / filepath

        # Security: Validate file is within MEMORY_DIR
        try:
            filepath = filepath.resolve()
            memory_dir_resolved = MEMORY_DIR.resolve()
            base = str(memory_dir_resolved)
            if str(filepath) != base and not str(filepath).startswith(base + os.sep):
                print(f"Error: File must be within {MEMORY_DIR}", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"Error validating path: {e}", file=sys.stderr)
            sys.exit(1)

        print(f"Indexing: {filepath}")
        index = build_index(single_file=filepath)
        print(f"✓ Index updated")

    elif args.rebuild:
        print("Rebuilding index...")
        index = build_index()
        print(f"\n✓ Indexed {len(index['files'])} blocks")

    elif args.list:
        list_files()

    elif args.search:
        results = search(args.search, limit=args.limit)

        if args.json:
            output = []
            for r in results:
                entry = r["entry"].copy()
                entry["content"] = get_file_content(entry["path"])
                entry["score"] = r["score"]
                output.append(entry)
            print(json.dumps(output, indent=2))
        else:
            display_results(results, verbose=args.verbose)

    else:
        # Default: build/update index
        index = build_index()
        print(f"\n✓ Indexed {len(index['files'])} blocks")


if __name__ == "__main__":
    main()
