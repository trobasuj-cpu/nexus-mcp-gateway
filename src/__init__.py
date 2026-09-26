"""NexusMCP Open Core Package Specification"""

from .protocol import JSONRPCRequest, JSONRPCResponse, MCPErrorCode, ToolDefinition, ToolExecutionResult
from .server import REGISTRY, run_server

__version__ = "1.0.0"
__all__ = [
    "JSONRPCRequest",
    "JSONRPCResponse",
    "MCPErrorCode",
    "ToolDefinition",
    "ToolExecutionResult",
    "REGISTRY",
    "run_server",
]
