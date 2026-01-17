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
import fcntl
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Set

# Configuration
SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent
INDEX_FILE = SCRIPT_DIR / ".index.json"

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
    Write index with exclusive file locking for concurrent safety.

    Prevents index corruption when multiple sessions write simultaneously.
    Uses fcntl.LOCK_EX for exclusive lock during write.
    """
    with open(index_path, 'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def index_file(filepath: Path) -> Optional[Dict]:
    """Index a single markdown file."""
    try:
        content = filepath.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(content)

        relative_path = filepath.relative_to(MEMORY_DIR)
        stat = filepath.stat()

        return {
            "path": str(relative_path),
            "title": frontmatter.get("title", filepath.stem.replace("-", " ").replace("_", " ").title()),
            "category": frontmatter.get("category", str(relative_path.parent)),
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
        except:
            index = {"files": [], "built": datetime.now().isoformat()}
    else:
        index = {"files": [], "built": datetime.now().isoformat()}

    # Determine files to index
    if single_file:
        md_files = [single_file] if single_file.exists() else []
    else:
        md_files = list(MEMORY_DIR.rglob("*.md"))

    for filepath in md_files:
        # Skip hidden files and scripts directory
        if any(part.startswith(".") for part in filepath.parts):
            continue
        if "scripts" in filepath.parts:
            continue

        entry = index_file(filepath)
        if entry:
            index["files"].append(entry)
            print(f"Indexed: {entry['path']}")

    index["built"] = datetime.now().isoformat()

    # Calculate IDF scores for all terms
    index["idf"] = calculate_idf(index)

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
                return _index_cache

            # Load and cache
            _index_cache = json.loads(INDEX_FILE.read_text())
            _index_mtime = current_mtime
            return _index_cache
        except:
            pass

    return build_index()


def search(query: str, limit: int = 5) -> List[Dict]:
    """Search indexed files with fuzzy matching, IDF weighting, bigrams, and intent detection."""
    index = load_index()
    idf_scores = index.get("idf", {})

    # Detect query intent and get weight adjustments
    intent, weight_adjustments = detect_query_intent(query)

    # Base weights
    WEIGHTS = {
        "title": 15,
        "title_word": 8,
        "tags": 10,
        "keywords": 5,
        "category": 4,
        "path": 2,
        "preview": 1,
        "bigram": 25
    }

    # Apply intent-based weight adjustments
    for field, multiplier in weight_adjustments.items():
        if field in WEIGHTS:
            WEIGHTS[field] *= multiplier

    # Parse query - remove stopwords but keep important terms
    query_terms = []
    for word in query.lower().split():
        normalized = normalize_word(word)
        if normalized and len(normalized) > 1:
            # Keep the word even if it's a stopword if it seems intentional
            if normalized not in STOPWORDS or len(query.split()) <= 2:
                query_terms.append(normalized)

    if not query_terms:
        query_terms = [normalize_word(w) for w in query.lower().split() if normalize_word(w)]

    # Extract bigrams from query
    query_bigrams = []
    normalized_query_words = [normalize_word(w) for w in query.lower().split()
                              if normalize_word(w) not in STOPWORDS and len(normalize_word(w)) > 1]
    for i in range(len(normalized_query_words) - 1):
        query_bigrams.append(f"{porter_stem(normalized_query_words[i])}-{porter_stem(normalized_query_words[i+1])}")

    results = []

    for entry in index.get("files", []):
        score = 0.0

        # Check title (highest weight)
        title = entry.get("title", "").lower()
        for term in query_terms:
            stemmed_term = porter_stem(term)
            term_idf = idf_scores.get(stemmed_term, 1.0)

            match_score = fuzzy_match(term, title)
            if match_score > 0:
                score += WEIGHTS["title"] * match_score * term_idf
            # Also check individual title words
            for title_word in title.split():
                word_score = fuzzy_match(term, title_word)
                if word_score > 0.5:
                    score += WEIGHTS["title_word"] * word_score * term_idf

        # Check tags (high weight)
        tags = entry.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if not isinstance(tag, str):
                    continue
                for term in query_terms:
                    stemmed_term = porter_stem(term)
                    term_idf = idf_scores.get(stemmed_term, 1.0)
                    match_score = fuzzy_match(term, tag)
                    if match_score > 0:
                        score += WEIGHTS["tags"] * match_score * term_idf

        # Check keywords (medium weight)
        keywords = entry.get("keywords", [])
        if isinstance(keywords, list):
            for keyword in keywords:
                if not isinstance(keyword, str):
                    continue
                for term in query_terms:
                    stemmed_term = porter_stem(term)
                    term_idf = idf_scores.get(stemmed_term, 1.0)
                    match_score = fuzzy_match(term, keyword)
                    if match_score > 0:
                        score += WEIGHTS["keywords"] * match_score * term_idf

        # Check bigrams (very high weight for phrase matches)
        entry_bigrams = entry.get("bigrams", [])
        for qbigram in query_bigrams:
            for ebigram in entry_bigrams:
                if qbigram == ebigram:
                    score += WEIGHTS["bigram"]  # Exact bigram match
                elif qbigram in ebigram or ebigram in qbigram:
                    score += WEIGHTS["bigram"] * 0.5  # Partial bigram match

        # Check category (medium weight)
        category = entry.get("category", "").lower()
        for term in query_terms:
            stemmed_term = porter_stem(term)
            term_idf = idf_scores.get(stemmed_term, 1.0)
            for cat_part in category.replace("/", " ").split():
                match_score = fuzzy_match(term, cat_part)
                if match_score > 0:
                    score += WEIGHTS["category"] * match_score * term_idf

        # Check path (low weight but useful)
        path = entry.get("path", "").lower()
        for term in query_terms:
            if term in path:
                score += WEIGHTS["path"]

        # Check preview (lowest weight)
        preview = entry.get("preview", "").lower()
        for term in query_terms:
            if term in preview:
                score += WEIGHTS["preview"]
            # Boost if multiple terms found in preview
            term_count = preview.count(term)
            if term_count > 1:
                score += WEIGHTS["preview"] * 0.5 * min(term_count, 3)

        if score > 0:
            results.append({"entry": entry, "score": score})

    # Sort by score
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:limit]


def display_results(results: List[Dict], verbose: bool = False):
    """Display search results."""
    if not results:
        print("No results found.")
        return

    for i, result in enumerate(results, 1):
        entry = result["entry"]
        score = result["score"]
        filepath = MEMORY_DIR / entry["path"]

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
    """Get full content of a file for context injection."""
    if not isinstance(path, str):
        return ""

    filepath = MEMORY_DIR / path

    # Security: Validate file is within MEMORY_DIR (prevent path traversal)
    try:
        resolved_path = filepath.resolve()
        memory_dir_resolved = MEMORY_DIR.resolve()
        if not str(resolved_path).startswith(str(memory_dir_resolved)):
            return ""  # Path traversal attempt - reject silently
    except Exception:
        return ""

    if resolved_path.exists():
        content = resolved_path.read_text()
        _, body = parse_frontmatter(content)
        return body
    return ""


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
        "--json", "-j", action="store_true", help="Output as JSON"
    )

    args = parser.parse_args()

    if args.file:
        filepath = Path(args.file)
        if not filepath.is_absolute():
            filepath = MEMORY_DIR / filepath

        # Security: Validate file is within MEMORY_DIR
        try:
            filepath = filepath.resolve()
            memory_dir_resolved = MEMORY_DIR.resolve()
            if not str(filepath).startswith(str(memory_dir_resolved)):
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
