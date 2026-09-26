"""
NexusMCP Protocol Specification & Wire Schema (MCP 2026 Compliant)
Implements Model Context Protocol JSON-RPC 2.0 specification for stateless HTTP and SSE transports.
Zero external stub dependencies; fully compilable and strictly typed.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class MCPErrorCode(int, Enum):
    """Standard JSON-RPC 2.0 & MCP protocol error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    RESOURCE_NOT_FOUND = -32001
    TOOL_EXECUTION_ERROR = -32002
    RATE_LIMIT_EXCEEDED = -32003
    AUTH_FORBIDDEN = -32004


@dataclass(frozen=True)
class ToolParameterSchema:
    """JSON Schema definition for tool arguments."""
    type: str = "object"
    properties: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    additionalProperties: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "properties": self.properties,
            "required": self.required,
            "additionalProperties": self.additionalProperties
        }


@dataclass
class ToolDefinition:
    """Formal MCP tool descriptor exposed to LLM clients (Claude, Cursor, GPT)."""
    name: str
    description: str
    inputSchema: ToolParameterSchema

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema.to_dict()
        }


@dataclass
class TextContent:
    """Standard text content block returned from MCP tool invocation."""
    text: str
    type: str = "text"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "text": self.text}


@dataclass
class ToolExecutionResult:
    """Structured response payload returned to MCP caller."""
    content: List[Dict[str, Any]]
    isError: bool = False

    @classmethod
    def success(cls, text: str) -> "ToolExecutionResult":
        return cls(content=[TextContent(text=text).to_dict()], isError=False)

    @classmethod
    def failure(cls, error_message: str) -> "ToolExecutionResult":
        return cls(content=[TextContent(text=f"ERROR: {error_message}").to_dict()], isError=True)

    def to_dict(self) -> Dict[str, Any]:
        return {"content": self.content, "isError": self.isError}


@dataclass
class JSONRPCRequest:
    """Inbound JSON-RPC 2.0 message."""
    jsonrpc: str
    method: str
    id: Optional[Union[str, int]] = None
    params: Optional[Dict[str, Any]] = None

    @classmethod
    def parse_raw(cls, raw_data: Union[str, bytes, dict]) -> "JSONRPCRequest":
        if isinstance(raw_data, (str, bytes)):
            payload = json.loads(raw_data)
        else:
            payload = raw_data

        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")
        if payload.get("jsonrpc") != "2.0":
            raise ValueError("Protocol violation: jsonrpc must be '2.0'")
        if "method" not in payload or not isinstance(payload["method"], str):
            raise ValueError("Method must be a non-empty string")

        return cls(
            jsonrpc="2.0",
            method=payload["method"],
            id=payload.get("id"),
            params=payload.get("params", {})
        )


@dataclass
class JSONRPCResponse:
    """Outbound JSON-RPC 2.0 response."""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def create_result(cls, req_id: Optional[Union[str, int]], result: Dict[str, Any]) -> "JSONRPCResponse":
        return cls(id=req_id, result=result, error=None)

    @classmethod
    def create_error(cls, req_id: Optional[Union[str, int]], code: MCPErrorCode, message: str, data: Optional[Any] = None) -> "JSONRPCResponse":
        err_body: Dict[str, Any] = {"code": int(code), "message": message}
        if data is not None:
            err_body["data"] = data
        return cls(id=req_id, result=None, error=err_body)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            out["error"] = self.error
        else:
            out["result"] = self.result if self.result is not None else {}
        return out

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
