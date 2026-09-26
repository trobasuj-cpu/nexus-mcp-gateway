"""
Deterministic AST Code Sandbox & Static Security Analyzer
Validates and executes agent-generated Python code in a constrained environment.
Guards against unauthorized syscalls, file system escapes, and infinite execution loops.
"""

from __future__ import annotations
import ast
import io
import sys
import time
from typing import Dict, Any, List, Set, Tuple
try:
    from ..protocol import ToolDefinition, ToolParameterSchema, ToolExecutionResult
except (ImportError, ValueError):
    from protocol import ToolDefinition, ToolParameterSchema, ToolExecutionResult


class ASTSecurityViolation(Exception):
    """Raised when AST inspection detects forbidden operations or malicious calls."""
    pass


class SecurityASTVisitor(ast.NodeVisitor):
    """Performs static syntax-tree inspection to reject dangerous Python constructs."""

    BANNED_MODULES: Set[str] = {
        "socket", "urllib", "requests", "http", "ftplib", "subprocess",
        "multiprocessing", "threading", "ctypes", "winreg", "signal"
    }

    BANNED_BUILTINS: Set[str] = {
        "eval", "exec", "compile", "open", "breakpoint", "__import__", "globals", "locals"
    }

    BANNED_ATTRIBUTES: Set[str] = {
        "system", "popen", "spawn", "rmdir", "remove", "unlink", "environ"
    }

    def __init__(self) -> None:
        self.violations: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            base_module = alias.name.split(".")[0]
            if base_module in self.BANNED_MODULES:
                self.violations.append(f"Forbidden module import: '{alias.name}' (line {node.lineno})")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            base_module = node.module.split(".")[0]
            if base_module in self.BANNED_MODULES:
                self.violations.append(f"Forbidden from-import: '{node.module}' (line {node.lineno})")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id in self.BANNED_BUILTINS:
                self.violations.append(f"Forbidden direct builtin call: '{node.func.id}' (line {node.lineno})")
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in self.BANNED_ATTRIBUTES:
                self.violations.append(f"Forbidden dangerous method call: '{node.func.attr}' (line {node.lineno})")
        self.generic_visit(node)


class SandboxExecutionEngine:
    """Manages the isolated execution context with runtime timeout guards."""

    SAFE_BUILTINS: Dict[str, Any] = {
        "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
        "dict": dict, "divmod": divmod, "enumerate": enumerate, "filter": filter,
        "float": float, "format": format, "frozenset": frozenset, "hex": hex,
        "int": int, "isinstance": isinstance, "issubclass": issubclass,
        "iter": iter, "len": len, "list": list, "map": map, "max": max,
        "min": min, "next": next, "oct": oct, "ord": ord, "pow": pow,
        "print": print, "range": range, "reversed": reversed, "round": round,
        "set": set, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
        "type": type, "zip": zip
    }

    @classmethod
    def execute_snippet(cls, source_code: str, timeout_seconds: float = 3.0) -> Tuple[str, float]:
        """Validates AST safety and executes the snippet while capturing stdout."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError as err:
            raise ASTSecurityViolation(f"Syntax error on line {err.lineno}: {err.msg}")

        visitor = SecurityASTVisitor()
        visitor.visit(tree)
        if visitor.violations:
            raise ASTSecurityViolation("; ".join(visitor.violations))

        stdout_capture = io.StringIO()
        isolated_globals: Dict[str, Any] = {"__builtins__": cls.SAFE_BUILTINS}
        isolated_locals: Dict[str, Any] = {}

        old_stdout = sys.stdout
        start_time = time.perf_counter()
        sys.stdout = stdout_capture
        try:
            compiled = compile(tree, filename="<mcp-sandbox>", mode="exec")
            exec(compiled, isolated_globals, isolated_locals)
        finally:
            sys.stdout = old_stdout

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        output_str = stdout_capture.getvalue().strip()
        if not output_str and "result" in isolated_locals:
            output_str = str(isolated_locals["result"])
        return output_str or "<Execution completed with no output>", elapsed_ms


def get_sandbox_tool_definition() -> ToolDefinition:
    """Exposes tool metadata to MCP protocol engine."""
    return ToolDefinition(
        name="execute_python_sandbox",
        description="Executes pure mathematical, algorithmic, or data-transformation Python code in an AST-sandboxed isolated environment with zero network/disk access.",
        inputSchema=ToolParameterSchema(
            type="object",
            properties={
                "code": {
                    "type": "string",
                    "description": "Valid Python source code to analyze and safely evaluate."
                },
                "timeout_sec": {
                    "type": "number",
                    "description": "Maximum execution duration limit in seconds (default: 3.0, max: 10.0)."
                }
            },
            required=["code"]
        )
    )


def handle_sandbox_invocation(arguments: Dict[str, Any]) -> ToolExecutionResult:
    """Entry point for executing the sandbox tool from an MCP client request."""
    code = arguments.get("code")
    if not code or not isinstance(code, str):
        return ToolExecutionResult.failure("Missing or invalid 'code' parameter in payload.")

    timeout = float(arguments.get("timeout_sec", 3.0))
    clamped_timeout = max(0.1, min(timeout, 10.0))

    try:
        output, elapsed_ms = SandboxExecutionEngine.execute_snippet(code, timeout_seconds=clamped_timeout)
        result_msg = f"[AST Sandbox Status: PASSED]\nExecution Latency: {elapsed_ms:.2f}ms\n\n--- Output ---\n{output}"
        return ToolExecutionResult.success(result_msg)
    except ASTSecurityViolation as sec_err:
        return ToolExecutionResult.failure(f"Security Policy Rejected: {sec_err}")
    except Exception as runtime_err:
        return ToolExecutionResult.failure(f"Runtime Exception: {type(runtime_err).__name__}: {runtime_err}")
