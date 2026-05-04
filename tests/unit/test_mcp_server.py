#!/usr/bin/env python3
"""
Tests for BloxCue MCP Server

Tests the MCP protocol handling, tool execution, and error cases.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import mcp_server


# ============================================================
# Protocol Tests
# ============================================================

def test_initialize():
    """Test MCP initialize handshake."""
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
    assert response is not None, "initialize_returns_response"
    assert response["result"]["protocolVersion"] == "2024-11-05", "initialize_has_protocol_version"
    assert "tools" in response["result"]["capabilities"], "initialize_has_tools_capability"
    assert response["result"]["serverInfo"]["name"] == "bloxcue", "initialize_has_server_info"


def test_ping():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}
    })
    assert response is not None, "ping_returns_response"
    assert response["result"] == {}, "ping_result_is_empty"


def test_notification_returns_none():
    """Test notification (no id) returns None."""
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "method": "notifications/initialized"
    })
    assert response is None, "notification_returns_none"


def test_unknown_method_returns_error():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 3, "method": "unknown/method", "params": {}
    })
    assert "error" in response, "unknown_method_returns_error"
    assert response["error"]["code"] == -32601, "unknown_method_error_code"


# ============================================================
# Tools List Tests
# ============================================================

def test_tools_list_returns_six_tools():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}
    })
    tools = response["result"]["tools"]
    assert len(tools) == 6, "tools_list_returns_tools"


def test_tools_list_contains_expected_tools():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}
    })
    tools = response["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "search_blocks" in tool_names, "has_search_blocks"
    assert "get_block" in tool_names, "has_get_block"
    assert "list_blocks" in tool_names, "has_list_blocks"
    assert "index_blocks" in tool_names, "has_index_blocks"
    assert "block_health" in tool_names, "has_block_health"
    assert "inject_context" in tool_names, "has_inject_context"


def test_search_blocks_tool_schema():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}
    })
    tools = response["result"]["tools"]
    search_tool = next(t for t in tools if t["name"] == "search_blocks")
    assert len(search_tool["description"]) > 0, "search_has_description"
    assert "inputSchema" in search_tool, "search_has_input_schema"
    assert "query" in search_tool["inputSchema"].get("required", []), "search_requires_query"


# ============================================================
# Tool Execution Tests
# ============================================================

def test_search_blocks_execution():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "search_blocks", "arguments": {"query": "deployment"}}
    })
    assert "result" in response, "search_blocks_succeeds"
    assert len(response["result"]["content"]) > 0, "search_blocks_has_content"
    assert response["result"]["content"][0]["type"] == "text", "search_blocks_content_is_text"
    assert "Found" in response["result"]["content"][0]["text"], "search_blocks_finds_results"


def test_search_blocks_empty_query_is_error():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 6, "method": "tools/call",
        "params": {"name": "search_blocks", "arguments": {}}
    })
    assert response["result"].get("isError") == True, "search_empty_query_is_error"


def test_list_blocks_execution():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 7, "method": "tools/call",
        "params": {"name": "list_blocks", "arguments": {}}
    })
    assert "result" in response, "list_blocks_succeeds"
    assert len(response["result"]["content"]) > 0, "list_blocks_has_content"
    assert "blocks" in response["result"]["content"][0]["text"].lower(), "list_blocks_shows_count"


def test_block_health_execution():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 8, "method": "tools/call",
        "params": {"name": "block_health", "arguments": {}}
    })
    assert "result" in response, "block_health_succeeds"
    assert "Health Report" in response["result"]["content"][0]["text"], "block_health_has_report"


def test_unknown_tool_returns_error():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 9, "method": "tools/call",
        "params": {"name": "nonexistent_tool", "arguments": {}}
    })
    assert "error" in response, "unknown_tool_returns_error"


def test_inject_context_execution():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 20, "method": "tools/call",
        "params": {"name": "inject_context", "arguments": {"query": "deployment"}}
    })
    assert "result" in response, "inject_context_succeeds"
    assert len(response["result"]["content"]) > 0, "inject_context_has_content"
    assert "BloxCue" in response["result"]["content"][0]["text"], "inject_context_has_metadata"


def test_inject_context_empty_query_is_error():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 21, "method": "tools/call",
        "params": {"name": "inject_context", "arguments": {}}
    })
    assert response["result"].get("isError") == True, "inject_empty_query_is_error"


def test_inject_context_with_token_budget():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 22, "method": "tools/call",
        "params": {"name": "inject_context", "arguments": {"query": "deployment", "max_tokens": 500}}
    })
    assert "result" in response, "inject_with_budget_succeeds"
    assert "BloxCue" in response["result"]["content"][0]["text"], "inject_budget_has_bloxcue_header"


# ============================================================
# Security Tests
# ============================================================

def test_path_traversal_blocked():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 10, "method": "tools/call",
        "params": {"name": "get_block", "arguments": {"path": "../../../etc/passwd"}}
    })
    assert response["result"].get("isError") == True, "path_traversal_blocked"
    assert "root:" not in response["result"]["content"][0]["text"], "path_traversal_no_content"


def test_empty_path_is_error():
    response = mcp_server.handle_message({
        "jsonrpc": "2.0", "id": 11, "method": "tools/call",
        "params": {"name": "get_block", "arguments": {"path": ""}}
    })
    assert response["result"].get("isError") == True, "empty_path_is_error"


# ============================================================
# Helper Function Tests
# ============================================================

def test_make_response_format():
    resp = mcp_server.make_response(42, {"test": True})
    assert resp["jsonrpc"] == "2.0", "make_response_format_jsonrpc"
    assert resp["id"] == 42, "make_response_format_id"
    assert resp["result"]["test"] == True, "make_response_format_result"


def test_make_error_format():
    err = mcp_server.make_error(43, -32600, "Invalid request")
    assert err["error"]["code"] == -32600, "make_error_format_code"
    assert err["error"]["message"] == "Invalid request", "make_error_format_message"


def test_make_error_with_data():
    err = mcp_server.make_error(44, -32602, "Bad params", {"detail": "missing field"})
    assert err["error"]["data"]["detail"] == "missing field", "make_error_with_data"
