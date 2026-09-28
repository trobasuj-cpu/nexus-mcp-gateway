"""
NexusMCP Production Stateless Server Engine (MCP 2026 Wire Protocol)
Provides stateless HTTP POST (/mcp), SSE streaming (/sse), and Kubernetes health check endpoints.
Executes with zero mandatory external framework dependencies (pure standard library HTTP / JSON-RPC).
"""

from __future__ import annotations
import json
import logging
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Callable
try:
    from .protocol import (
        JSONRPCRequest,
        JSONRPCResponse,
        MCPErrorCode,
        ToolDefinition,
        ToolExecutionResult
    )
    from .tools import (
        get_sandbox_tool_definition, handle_sandbox_invocation,
        get_safe_sql_tool_definition, handle_sql_invocation,
        get_cost_router_tool_definition, handle_router_invocation
    )
    from .dashboard import get_dashboard_html, TELEMETRY
except (ImportError, ValueError):
    from protocol import (
        JSONRPCRequest,
        JSONRPCResponse,
        MCPErrorCode,
        ToolDefinition,
        ToolExecutionResult
    )
    from tools import (
        get_sandbox_tool_definition, handle_sandbox_invocation,
        get_safe_sql_tool_definition, handle_sql_invocation,
        get_cost_router_tool_definition, handle_router_invocation
    )
    from dashboard import get_dashboard_html, TELEMETRY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [NexusMCP] %(message)s")
logger = logging.getLogger("NexusMCP")

SERVER_START_TIME = time.time()
MCP_PROTOCOL_VERSION = "2024-11-05"


class ToolRegistry:
    """Manages active MCP tool definitions and dispatch handlers."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable[[Dict[str, Any]], ToolExecutionResult]] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.register(get_sandbox_tool_definition(), handle_sandbox_invocation)
        self.register(get_safe_sql_tool_definition(), handle_sql_invocation)
        self.register(get_cost_router_tool_definition(), handle_router_invocation)

    def register(self, definition: ToolDefinition, handler: Callable[[Dict[str, Any]], ToolExecutionResult]) -> None:
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler
        logger.info(f"Registered tool: '{definition.name}'")

    def list_tools(self) -> list[Dict[str, Any]]:
        return [tool.to_dict() for tool in self._tools.values()]

    def invoke(self, name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        if name not in self._handlers:
            raise KeyError(f"Tool '{name}' is not registered in this MCP gateway.")
        return self._handlers[name](arguments)


REGISTRY = ToolRegistry()


class MCPRequestHandler(BaseHTTPRequestHandler):
    """Processes inbound MCP JSON-RPC 2.0 requests with strict error boundary defense."""

    server_version = "NexusMCP/1.0.0"

    def _send_json_response(self, status_code: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_html_response(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        clean_path = self.path.split("?")[0]
        if clean_path in ("/", "/dashboard", "/index.html"):
            self._send_html_response(get_dashboard_html())
        elif clean_path == "/api/stats":
            self._send_json_response(200, TELEMETRY.get_stats())
        elif clean_path == "/health":
            uptime_sec = round(time.time() - SERVER_START_TIME, 2)
            self._send_json_response(200, {
                "status": "HEALTHY",
                "uptime_seconds": uptime_sec,
                "protocol_version": MCP_PROTOCOL_VERSION,
                "registered_tools_count": len(REGISTRY.list_tools())
            })
        elif clean_path == "/sse":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            event_data = f"event: endpoint\ndata: /mcp\n\n".encode("utf-8")
            self.wfile.write(event_data)
        else:
            self._send_json_response(404, {
                "error": "Not Found",
                "valid_endpoints": ["/", "/dashboard", "/api/stats", "/mcp", "/health", "/sse"]
            })

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""

        # 1. Interactive Simulator: AST Sandbox
        if self.path == "/api/test/sandbox":
            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
                code = payload.get("code", "")
                t0 = time.perf_counter()
                res = handle_sandbox_invocation({"code": code})
                elapsed = (time.perf_counter() - t0) * 1000.0
                status = "BLOCKED" if res.isError else "ALLOWED"
                reason = res.content[0]["text"] if res.isError else "AST security verification passed"
                TELEMETRY.record_event("execute_python_sandbox", "AST_SIMULATION", status, code, reason, elapsed)
                self._send_json_response(200, res.to_dict())
            except Exception as e:
                self._send_json_response(400, {"error": str(e)})
            return

        # 2. Interactive Simulator: Safe SQL
        if self.path == "/api/test/sql":
            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
                query = payload.get("query", "")
                t0 = time.perf_counter()
                res = handle_sql_invocation({"query": query})
                elapsed = (time.perf_counter() - t0) * 1000.0
                status = "BLOCKED" if res.isError else "ALLOWED"
                reason = res.content[0]["text"] if res.isError else "Query executed safely"
                TELEMETRY.record_event("safe_sql_query", "SQL_SIMULATION", status, query, reason, elapsed)
                self._send_json_response(200, res.to_dict())
            except Exception as e:
                self._send_json_response(400, {"error": str(e)})
            return

        # 3. Interactive Simulator: Cost Router
        if self.path == "/api/test/route":
            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
                t0 = time.perf_counter()
                res = handle_router_invocation(payload)
                elapsed = (time.perf_counter() - t0) * 1000.0
                desc = payload.get("task_description", "")
                TELEMETRY.record_event("calculate_model_route", "COST_OPTIMIZATION", "ROUTED", desc, "Cost router calculated optimal model tier", elapsed)
                self._send_json_response(200, res.to_dict())
            except Exception as e:
                self._send_json_response(400, {"error": str(e)})
            return

        # 4. Standard MCP 2026 Wire Protocol
        if self.path != "/mcp":
            self._send_json_response(404, {"error": "Invalid endpoint. Send MCP requests to /mcp"})
            return

        if content_length <= 0:
            resp = JSONRPCResponse.create_error(None, MCPErrorCode.PARSE_ERROR, "Empty request body")
            self._send_json_response(400, resp.to_dict())
            return

        try:
            req = JSONRPCRequest.parse_raw(raw_body)
        except Exception as parse_err:
            resp = JSONRPCResponse.create_error(None, MCPErrorCode.PARSE_ERROR, f"Malformed JSON-RPC: {parse_err}")
            self._send_json_response(400, resp.to_dict())
            return

        try:
            if req.method == "initialize":
                res_data = {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "NexusMCP-Gateway", "version": "1.0.0"}
                }
                out = JSONRPCResponse.create_result(req.id, res_data)
            elif req.method == "tools/list":
                out = JSONRPCResponse.create_result(req.id, {"tools": REGISTRY.list_tools()})
            elif req.method == "tools/call":
                params = req.params or {}
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                if not tool_name:
                    out = JSONRPCResponse.create_error(req.id, MCPErrorCode.INVALID_PARAMS, "Missing 'name' in tools/call")
                else:
                    t0 = time.perf_counter()
                    exec_result = REGISTRY.invoke(tool_name, arguments)
                    elapsed = (time.perf_counter() - t0) * 1000.0
                    status = "BLOCKED" if exec_result.isError else "ALLOWED"
                    preview = str(arguments)[:80]
                    TELEMETRY.record_event(tool_name, "MCP_WIRE_CALL", status, preview, "MCP agent invocation", elapsed)
                    out = JSONRPCResponse.create_result(req.id, exec_result.to_dict())
            elif req.method == "ping":
                out = JSONRPCResponse.create_result(req.id, {})
            else:
                out = JSONRPCResponse.create_error(req.id, MCPErrorCode.METHOD_NOT_FOUND, f"Method '{req.method}' not supported")

            self._send_json_response(200, out.to_dict())
        except KeyError as not_found:
            err = JSONRPCResponse.create_error(req.id, MCPErrorCode.METHOD_NOT_FOUND, str(not_found))
            self._send_json_response(200, err.to_dict())
        except Exception as internal_err:
            logger.error(f"Internal error processing {req.method}: {internal_err}", exc_info=True)
            err = JSONRPCResponse.create_error(req.id, MCPErrorCode.INTERNAL_ERROR, str(internal_err))
            self._send_json_response(200, err.to_dict())


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Launches the production HTTP daemon."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, MCPRequestHandler)
    logger.info(f"NexusMCP Gateway active on http://{host}:{port}/mcp (Health: /health, SSE: /sse)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Graceful shutdown requested. Terminating server...")
        httpd.server_close()


if __name__ == "__main__":
    port_env = int(os.environ.get("NEXUS_MCP_PORT", 8080))
    run_server(port=port_env)
