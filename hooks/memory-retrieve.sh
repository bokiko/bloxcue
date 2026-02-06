#!/bin/bash
#
# bloxcue Auto-Retrieval Hook
#
# Automatically injects relevant context blocks when user prompts
# contain matching keywords.
#
# Install: Copy to ~/.claude/hooks/ and add to settings.json
#
# Debug: Set BLOXCUE_DEBUG=1 to see what's happening
#

set -e

# Configuration - Updated by install.sh
MEMORY_PATH="$HOME/.claude-memory"
MAX_RESULTS=3
MAX_CONTEXT_CHARS=3000
MIN_QUERY_LENGTH=5

# Debug mode
DEBUG="${BLOXCUE_DEBUG:-0}"

debug_log() {
    if [ "$DEBUG" = "1" ]; then
        echo "[bloxcue] $1" >&2
    fi
}

# Read input from Claude
INPUT=$(cat)

debug_log "Received input"

# Extract and sanitize user message using Python
USER_MESSAGE=$(echo "$INPUT" | python3 -c "
import sys, json, re
try:
    data = json.load(sys.stdin)
    msg = data.get('user_prompt', '')
    # Sanitize: remove control characters and limit length
    msg = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', msg)
    msg = msg[:500]  # Limit to 500 chars for search
    print(msg)
except Exception as e:
    pass
" 2>/dev/null)

# CVE-1 fix: Strip shell metacharacters to prevent command injection
# Without this, USER_MESSAGE containing $(cmd) or backticks would execute in subsequent expansions
USER_MESSAGE=$(printf '%s' "$USER_MESSAGE" | tr -d '`$();&|\\'"'"'{}')

debug_log "User message: ${USER_MESSAGE:0:50}..."

# Skip if no message or too short
if [ -z "$USER_MESSAGE" ] || [ ${#USER_MESSAGE} -lt $MIN_QUERY_LENGTH ]; then
    debug_log "Message too short, skipping"
    echo '{"result": "continue"}'
    exit 0
fi

# Skip common non-contextual messages
SKIP_PATTERNS=(
    "^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|sure|got it)$"
    "^(what|how|why|can you|could you|please|help)$"
    "^[0-9]+$"
)

LOWER_MSG=$(echo "$USER_MESSAGE" | tr '[:upper:]' '[:lower:]' | xargs)
for pattern in "${SKIP_PATTERNS[@]}"; do
    if echo "$LOWER_MSG" | grep -qiE "$pattern"; then
        debug_log "Skipping common phrase: $LOWER_MSG"
        echo '{"result": "continue"}'
        exit 0
    fi
done

# Check if indexer exists
if [ ! -f "$MEMORY_PATH/scripts/indexer.py" ]; then
    debug_log "Indexer not found at $MEMORY_PATH/scripts/indexer.py"
    echo '{"result": "continue"}'
    exit 0
fi

# Search memory for relevant context
debug_log "Searching for: $USER_MESSAGE"
SEARCH_RESULTS=$(python3 "$MEMORY_PATH/scripts/indexer.py" --search "$USER_MESSAGE" --limit $MAX_RESULTS --json 2>/dev/null || echo "[]")

# Check if we have results
RESULT_COUNT=$(echo "$SEARCH_RESULTS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    # Only count results with meaningful scores
    good_results = [r for r in data if r.get('score', 0) > 5]
    print(len(good_results))
except:
    print(0)
" 2>/dev/null || echo "0")

debug_log "Found $RESULT_COUNT relevant results"

if [ "$RESULT_COUNT" = "0" ]; then
    debug_log "No relevant results, skipping"
    echo '{"result": "continue"}'
    exit 0
fi

# CVE-2 fix: Pipe SEARCH_RESULTS via stdin instead of heredoc interpolation.
# The old heredoc approach embedded $SEARCH_RESULTS in a Python triple-quoted string,
# allowing content containing ''' to escape the string and inject arbitrary Python.
CONTEXT=$(echo "$SEARCH_RESULTS" | python3 -c "
import json, sys

try:
    results = json.load(sys.stdin)
except Exception:
    results = []

if not results:
    sys.exit(0)

output = []
total_chars = 0
max_chars = $MAX_CONTEXT_CHARS

good_results = [r for r in results if r.get('score', 0) > 5]

for r in good_results:
    title = r.get('title', 'Unknown')
    path = r.get('path', '')
    content = r.get('content', '')
    score = r.get('score', 0)

    if score > 20:
        max_content = 800
    elif score > 10:
        max_content = 500
    else:
        max_content = 300

    content = content[:max_content]
    if len(r.get('content', '')) > max_content:
        content += '...'

    entry = f'### {title}\n*Source: {path}*\n\n{content}\n'

    if total_chars + len(entry) > max_chars:
        break

    output.append(entry)
    total_chars += len(entry)

if output:
    header = '\U0001f4da **Relevant context from bloxcue:**\n\n'
    print(header + '\n---\n'.join(output))
")

# Output result
if [ -n "$CONTEXT" ]; then
    debug_log "Injecting context (${#CONTEXT} chars)"

    # Escape for JSON
    ESCAPED_CONTEXT=$(echo "$CONTEXT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

    echo "{\"result\": \"continue\", \"message\": $ESCAPED_CONTEXT}"
else
    debug_log "No context to inject"
    echo '{"result": "continue"}'
fi
