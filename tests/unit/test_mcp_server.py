#!/usr/bin/env python3
"""
Tests for BloxCue MCP Server

Tests the MCP protocol handling, tool execution, and error cases.
"""

import sys
import json
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import mcp_server

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}")
        failed += 1


def section(name):
    print(f"\n{name}")
    print("-" * 40)


# ============================================================
# Protocol Tests
# ============================================================
section("MCP Protocol Tests")

# Test initialize
response = mcp_server.handle_message({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }
})
check("initialize_returns_response", response is not None)
check("initialize_has_protocol_version", response["result"]["protocolVersion"] == "2024-11-05")
check("initialize_has_tools_capability", "tools" in response["result"]["capabilities"])
check("initialize_has_server_info", response["result"]["serverInfo"]["name"] == "bloxcue")

# Test ping
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}
})
check("ping_returns_response", response is not None)
check("ping_result_is_empty", response["result"] == {})

# Test notification (no id) returns None
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "method": "notifications/initialized"
})
check("notification_returns_none", response is None)

# Test unknown method
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 3, "method": "unknown/method", "params": {}
})
check("unknown_method_returns_error", "error" in response)
check("unknown_method_error_code", response["error"]["code"] == -32601)

# ============================================================
# Tools List Tests
# ============================================================
section("Tools List Tests")

response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}
})
tools = response["result"]["tools"]
check("tools_list_returns_tools", len(tools) == 6)
tool_names = [t["name"] for t in tools]
check("has_search_blocks", "search_blocks" in tool_names)
check("has_get_block", "get_block" in tool_names)
check("has_list_blocks", "list_blocks" in tool_names)
check("has_index_blocks", "index_blocks" in tool_names)
check("has_block_health", "block_health" in tool_names)
check("has_inject_context", "inject_context" in tool_names)

# Check tool schema format
search_tool = next(t for t in tools if t["name"] == "search_blocks")
check("search_has_description", len(search_tool["description"]) > 0)
check("search_has_input_schema", "inputSchema" in search_tool)
check("search_requires_query", "query" in search_tool["inputSchema"].get("required", []))

# ============================================================
# Tool Execution Tests
# ============================================================
section("Tool Execution Tests")

# Test search_blocks
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 5, "method": "tools/call",
    "params": {"name": "search_blocks", "arguments": {"query": "deployment"}}
})
check("search_blocks_succeeds", "result" in response)
check("search_blocks_has_content", len(response["result"]["content"]) > 0)
check("search_blocks_content_is_text", response["result"]["content"][0]["type"] == "text")
check("search_blocks_finds_results", "Found" in response["result"]["content"][0]["text"])

# Test search_blocks with empty query
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 6, "method": "tools/call",
    "params": {"name": "search_blocks", "arguments": {}}
})
check("search_empty_query_is_error", response["result"].get("isError") == True)

# Test list_blocks
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 7, "method": "tools/call",
    "params": {"name": "list_blocks", "arguments": {}}
})
check("list_blocks_succeeds", "result" in response)
check("list_blocks_has_content", len(response["result"]["content"]) > 0)
check("list_blocks_shows_count", "blocks" in response["result"]["content"][0]["text"].lower())

# Test block_health
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 8, "method": "tools/call",
    "params": {"name": "block_health", "arguments": {}}
})
check("block_health_succeeds", "result" in response)
check("block_health_has_report", "Health Report" in response["result"]["content"][0]["text"])

# Test unknown tool
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 9, "method": "tools/call",
    "params": {"name": "nonexistent_tool", "arguments": {}}
})
check("unknown_tool_returns_error", "error" in response)

# Test inject_context
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 20, "method": "tools/call",
    "params": {"name": "inject_context", "arguments": {"query": "deployment"}}
})
check("inject_context_succeeds", "result" in response)
check("inject_context_has_content", len(response["result"]["content"]) > 0)
check("inject_context_has_metadata", "BloxCue" in response["result"]["content"][0]["text"])

# Test inject_context with empty query
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 21, "method": "tools/call",
    "params": {"name": "inject_context", "arguments": {}}
})
check("inject_empty_query_is_error", response["result"].get("isError") == True)

# Test inject_context with token budget
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 22, "method": "tools/call",
    "params": {"name": "inject_context", "arguments": {"query": "deployment", "max_tokens": 500}}
})
check("inject_with_budget_succeeds", "result" in response)
check("inject_budget_has_bloxcue_header", "BloxCue" in response["result"]["content"][0]["text"])

# ============================================================
# Security Tests
# ============================================================
section("Security Tests")

# Test path traversal in get_block
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 10, "method": "tools/call",
    "params": {"name": "get_block", "arguments": {"path": "../../../etc/passwd"}}
})
check("path_traversal_blocked", response["result"].get("isError") == True)
check("path_traversal_no_content", "root:" not in response["result"]["content"][0]["text"])

# Test empty path
response = mcp_server.handle_message({
    "jsonrpc": "2.0", "id": 11, "method": "tools/call",
    "params": {"name": "get_block", "arguments": {"path": ""}}
})
check("empty_path_is_error", response["result"].get("isError") == True)

# ============================================================
# Helper Function Tests
# ============================================================
section("Helper Function Tests")

# Test make_response
resp = mcp_server.make_response(42, {"test": True})
check("make_response_format", resp["jsonrpc"] == "2.0" and resp["id"] == 42 and resp["result"]["test"] == True)

# Test make_error
err = mcp_server.make_error(43, -32600, "Invalid request")
check("make_error_format", err["error"]["code"] == -32600 and err["error"]["message"] == "Invalid request")

# Test make_error with data
err = mcp_server.make_error(44, -32602, "Bad params", {"detail": "missing field"})
check("make_error_with_data", err["error"]["data"]["detail"] == "missing field")

# ============================================================
# Summary
# ============================================================
print(f"\n{'='*60}")
print(f"Results: {passed}/{passed+failed} passed, {failed} failed")


if __name__ == "__main__":
    pass
