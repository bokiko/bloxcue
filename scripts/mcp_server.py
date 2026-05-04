#!/usr/bin/env python3
"""
BloxCue MCP Server

Exposes BloxCue's context retrieval as an MCP (Model Context Protocol) server.
Works with Claude Code, Codex, Gemini, Cursor, Windsurf, or any MCP-compatible client.

Usage:
    Add to your MCP config (e.g., ~/.claude/mcp_config.json):
    {
        "mcpServers": {
            "bloxcue": {
                "command": "python3",
                "args": ["/path/to/bloxcue/scripts/mcp_server.py"]
            }
        }
    }

Protocol: JSON-RPC 2.0 over stdio (newline-delimited messages)
Dependencies: None (Python 3.8+ stdlib only)
"""

import sys
import json
import os
from pathlib import Path
from typing import Optional

# Add scripts dir to path so we can import indexer
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

import indexer

# Server metadata
SERVER_NAME = "bloxcue"
SERVER_VERSION = "3.0.0"
PROTOCOL_VERSION = "2024-11-05"

# Tool definitions
TOOLS = [
    {
        "name": "search_blocks",
        "description": "Search BloxCue knowledge blocks for relevant context. Returns ranked results matching the query using BM25 scoring, IDF weighting, bigram matching, and query intent detection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., 'deployment guide', 'how to fix auth errors')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_block",
        "description": "Get the full content of a specific knowledge block by its path. Use after search_blocks to retrieve the complete content of a relevant block.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the block file (e.g., 'guides/deployment.md')"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_blocks",
        "description": "List all indexed knowledge blocks, optionally filtered by category.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category (e.g., 'guides', 'references'). Omit to list all."
                }
            }
        }
    },
    {
        "name": "index_blocks",
        "description": "Rebuild the BloxCue search index. Run this after adding or modifying block files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Force full rebuild (default: false)",
                    "default": False
                }
            }
        }
    },
    {
        "name": "block_health",
        "description": "Get a health report for your knowledge blocks: freshness, coverage, and suggestions for improvement.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "inject_context",
        "description": "Search and inject relevant context from markdown blocks and SQLite learned memory with smart token budgeting. Returns deduplicated, priority-ranked content formatted for LLM consumption. Use this instead of search_blocks + get_block for one-shot context retrieval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., 'deployment guide', 'how to fix auth errors')"
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Token budget for injected context (default: 3000)",
                    "default": 3000
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum blocks to consider (default: 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
]


def handle_search_blocks(arguments: dict) -> dict:
    """Execute search_blocks tool."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 5)

    if not query or not isinstance(query, str):
        return {"content": [{"type": "text", "text": "Error: query must be a non-empty string"}], "isError": True}

    # M-2 fix: Cap limit to prevent excessive resource usage
    limit = min(max(int(limit) if isinstance(limit, (int, float)) else 5, 1), 100)

    results = indexer.search(query, limit=limit)

    if not results:
        return {"content": [{"type": "text", "text": f"No blocks found matching: {query}"}]}

    lines = [f"Found {len(results)} block(s) for: \"{query}\"\n"]
    for i, result in enumerate(results, 1):
        entry = result["entry"]
        score = result["score"]
        tags = entry.get("tags", [])
        tags_str = ", ".join(str(t) for t in tags if t) if isinstance(tags, list) else str(tags)
        source_label = ""
        if entry.get("source") == "pg":
            source_label = " [legacy PG]"
        elif entry.get("source") == "sqlite":
            source_label = " [learning]"

        lines.append(f"{i}. **{entry['title']}**{source_label} (score: {score:.1f})")
        lines.append(f"   Path: {entry['path']}")
        lines.append(f"   Category: {entry['category']}")
        if tags_str:
            lines.append(f"   Tags: {tags_str}")
        lines.append(f"   Preview: {entry.get('preview', '')[:150]}...")
        lines.append("")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def handle_get_block(arguments: dict) -> dict:
    """Execute get_block tool."""
    path = arguments.get("path", "")

    if not path:
        return {"content": [{"type": "text", "text": "Error: path is required"}], "isError": True}

    content = indexer.get_file_content(path)

    if not content:
        return {"content": [{"type": "text", "text": f"Block not found: {path}"}], "isError": True}

    # Get metadata from index
    index = indexer.load_index()
    metadata = None
    for entry in index.get("files", []):
        if entry.get("path") == path:
            metadata = entry
            break

    lines = []
    if metadata:
        lines.append(f"# {metadata.get('title', path)}")
        tags = metadata.get("tags", [])
        if tags:
            tags_str = ", ".join(str(t) for t in tags if t) if isinstance(tags, list) else str(tags)
            lines.append(f"Tags: {tags_str}")
        lines.append(f"Category: {metadata.get('category', 'unknown')}")
        lines.append(f"Modified: {metadata.get('modified', 'unknown')}")
        lines.append("---")

    lines.append(content)

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def handle_list_blocks(arguments: dict) -> dict:
    """Execute list_blocks tool."""
    category_filter = arguments.get("category", "")
    index = indexer.load_index()
    files = index.get("files", [])

    if not files:
        return {"content": [{"type": "text", "text": "No blocks indexed. Add markdown files and run index_blocks."}]}

    # Group by category
    by_category: dict = {}
    for entry in files:
        cat = entry.get("category", "uncategorized")
        if category_filter and cat != category_filter:
            continue
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(entry)

    if not by_category:
        return {"content": [{"type": "text", "text": f"No blocks found in category: {category_filter}"}]}

    total = sum(len(v) for v in by_category.values())
    pg_count = sum(1 for entries in by_category.values() for e in entries if e.get("source") == "pg")
    sqlite_count = sum(1 for entries in by_category.values() for e in entries if e.get("source") == "sqlite")
    file_count = total - pg_count - sqlite_count
    if pg_count > 0 or sqlite_count > 0:
        lines = [f"**{total} blocks** indexed ({file_count} file, {sqlite_count} learning, {pg_count} legacy PG)\n"]
    else:
        lines = [f"**{total} blocks** indexed\n"]

    for category in sorted(by_category.keys()):
        lines.append(f"### {category}/")
        for entry in sorted(by_category[category], key=lambda x: x.get("title", "")):
            tags = entry.get("tags", [])
            tags_str = ""
            if tags and isinstance(tags, list):
                tags_str = f" [{', '.join(str(t) for t in tags[:3] if t)}]"
            lines.append(f"  - {entry['title']}{tags_str} ({entry['path']})")
        lines.append("")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def handle_index_blocks(arguments: dict) -> dict:
    """Execute index_blocks tool."""
    # Redirect stdout to capture indexer output
    old_stdout = sys.stdout
    devnull = open(os.devnull, 'w')
    sys.stdout = devnull
    try:
        index = indexer.build_index()
    finally:
        sys.stdout = old_stdout
        devnull.close()

    file_count = len(index.get("files", []))
    idf_count = len(index.get("idf", {}))

    return {
        "content": [{
            "type": "text",
            "text": f"Index rebuilt successfully.\n- Blocks indexed: {file_count}\n- Unique terms (IDF): {idf_count}\n- Built: {index.get('built', 'unknown')}"
        }]
    }


def handle_block_health(arguments: dict) -> dict:
    """Execute block_health tool. Delegates to indexer's generate_health_report()."""
    report = indexer.generate_health_report()
    return {"content": [{"type": "text", "text": report}]}


def handle_inject_context(arguments: dict) -> dict:
    """Execute inject_context tool. Smart token-budgeted context injection."""
    query = arguments.get("query", "")
    max_tokens = arguments.get("max_tokens", 3000)
    limit = arguments.get("limit", 5)

    if not query or not isinstance(query, str):
        return {"content": [{"type": "text", "text": "Error: query must be a non-empty string"}], "isError": True}

    # M-2 fix: Cap values to prevent excessive resource usage
    if not isinstance(max_tokens, int) or max_tokens < 1:
        max_tokens = 3000
    else:
        max_tokens = min(max_tokens, 50000)
    if not isinstance(limit, int) or limit < 1:
        limit = 5
    else:
        limit = min(limit, 100)

    result = indexer.inject_context(query, limit=limit, max_tokens=max_tokens)
    return {"content": [{"type": "text", "text": result}]}


# Tool dispatch
TOOL_HANDLERS = {
    "search_blocks": handle_search_blocks,
    "get_block": handle_get_block,
    "list_blocks": handle_list_blocks,
    "index_blocks": handle_index_blocks,
    "block_health": handle_block_health,
    "inject_context": handle_inject_context,
}


def make_response(id, result):
    """Create a JSON-RPC success response."""
    return {"jsonrpc": "2.0", "id": id, "result": result}


def make_error(id, code, message, data=None):
    """Create a JSON-RPC error response."""
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": error}


def handle_message(message: dict) -> Optional[dict]:
    """Handle a single JSON-RPC message. Returns response dict or None for notifications."""
    method = message.get("method", "")
    msg_id = message.get("id")
    params = message.get("params", {})

    # Notifications (no id) don't get responses
    if msg_id is None:
        return None

    if method == "initialize":
        return make_response(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION
            }
        })

    elif method == "ping":
        return make_response(msg_id, {})

    elif method == "tools/list":
        return make_response(msg_id, {
            "tools": TOOLS
        })

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return make_error(msg_id, -32602, f"Unknown tool: {tool_name}")

        try:
            result = handler(arguments)
            return make_response(msg_id, result)
        except Exception as e:
            # L-2 fix: Log full error to stderr, return generic message to client
            sys.stderr.write(f"Error executing {tool_name}: {e}\n")
            sys.stderr.flush()
            return make_response(msg_id, {
                "content": [{"type": "text", "text": f"Internal error executing {tool_name}"}],
                "isError": True
            })

    else:
        return make_error(msg_id, -32601, f"Method not found: {method}")


def send_message(message: dict):
    """Write a JSON-RPC message to stdout (newline-delimited)."""
    line = json.dumps(message, separators=(',', ':'))
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def main():
    """Main event loop: read JSON-RPC messages from stdin, write responses to stdout."""
    # Log to stderr (allowed by MCP spec)
    sys.stderr.write(f"BloxCue MCP Server v{SERVER_VERSION} starting...\n")
    sys.stderr.write(f"Memory directory: {indexer.MEMORY_DIR}\n")
    sys.stderr.write(f"Learnings database: {indexer.LEARNINGS_DB}\n")
    pg_status = "disabled"
    if getattr(indexer, 'HAS_PG_PROVIDER', False) and indexer.PG_ENABLED:
        pg_status = "enabled"
    elif getattr(indexer, 'HAS_PG_PROVIDER', False):
        pg_status = "available but disabled"
    sys.stderr.write(f"Legacy PostgreSQL runtime: {pg_status}\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError as e:
            send_message(make_error(None, -32700, f"Parse error: {str(e)}"))
            continue

        response = handle_message(message)
        if response is not None:
            send_message(response)


if __name__ == "__main__":
    main()
