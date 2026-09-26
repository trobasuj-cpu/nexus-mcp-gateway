"""
Deterministic Unit-Test Harness for MCP 2026 Wire Protocol Engine
Validates JSON-RPC 2.0 parsing, capability handshakes, and tool dispatch.
Part of NexusMCP Pillar 2: Deterministic Verification Harness.
"""

import json
import pytest
import sys
from pathlib import Path

# Add src to pythonpath
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    MCPErrorCode
)
from server import REGISTRY


def test_jsonrpc_request_parsing_valid() -> None:
    """Verifies parsing of standard JSON-RPC 2.0 payloads."""
    raw = '{"jsonrpc": "2.0", "id": "req-101", "method": "tools/list", "params": {}}'
    req = JSONRPCRequest.parse_raw(raw)
    assert req.jsonrpc == "2.0"
    assert req.id == "req-101"
    assert req.method == "tools/list"
    assert req.params == {}


def test_jsonrpc_request_parsing_invalid_version() -> None:
    """Verifies that non-2.0 JSON-RPC versions are rejected."""
    raw = '{"jsonrpc": "1.0", "id": 1, "method": "ping"}'
    with pytest.raises(ValueError) as exc_info:
        JSONRPCRequest.parse_raw(raw)
    assert "Protocol violation" in str(exc_info.value)


def test_jsonrpc_response_formatting_result() -> None:
    """Verifies JSON-RPC success response generation."""
    resp = JSONRPCResponse.create_result("req-202", {"status": "ok", "value": 42})
    data = resp.to_dict()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == "req-202"
    assert data["result"]["status"] == "ok"
    assert "error" not in data


def test_jsonrpc_response_formatting_error() -> None:
    """Verifies JSON-RPC error payload formatting with standard error codes."""
    resp = JSONRPCResponse.create_error("req-303", MCPErrorCode.METHOD_NOT_FOUND, "Unknown method")
    data = resp.to_dict()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == "req-303"
    assert "result" not in data
    assert data["error"]["code"] == int(MCPErrorCode.METHOD_NOT_FOUND)
    assert data["error"]["message"] == "Unknown method"


def test_registry_contains_all_default_tools() -> None:
    """Verifies that the default tool registry exposes the triad of core tools."""
    tools = REGISTRY.list_tools()
    tool_names = [t["name"] for t in tools]
    assert "execute_python_sandbox" in tool_names
    assert "safe_sql_query" in tool_names
    assert "calculate_model_route" in tool_names
    assert len(tools) == 3


def test_tool_dispatch_cost_router() -> None:
    """Verifies end-to-end execution of the cost router tool via the registry."""
    args = {
        "task_description": "Implement a distributed Raft consensus algorithm with formal verification",
        "estimated_tokens": 15000,
        "max_budget_usd": 2.0
    }
    exec_result = REGISTRY.invoke("calculate_model_route", args)
    assert not exec_result.isError
    assert len(exec_result.content) == 1
    text = exec_result.content[0]["text"]
    assert "claude-5-fable" in text
    assert "FRONTIER_REASONING" in text


def test_unknown_tool_invocation_raises_keyerror() -> None:
    """Verifies that calling an unregistered tool raises a controlled KeyError."""
    with pytest.raises(KeyError) as exc_info:
        REGISTRY.invoke("non_existent_tool", {})
    assert "is not registered in this MCP gateway" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main(["-v", __file__])
