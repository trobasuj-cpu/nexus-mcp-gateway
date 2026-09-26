"""
Deterministic Unit-Test Harness for AST Python Sandbox
Validates strict containment, forbidden syscall blocks, and safe code evaluation.
Part of NexusMCP Pillar 2: Deterministic Verification Harness.
"""

import pytest
import sys
from pathlib import Path

# Add src to pythonpath
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from tools.ast_sandbox import (
    SandboxExecutionEngine,
    ASTSecurityViolation,
    handle_sandbox_invocation
)


def test_safe_mathematical_evaluation() -> None:
    """Verifies that legitimate arithmetic, list comprehensions, and algorithms succeed."""
    code = """
def sieve(n):
    primes = []
    for num in range(2, n + 1):
        if all(num % i != 0 for i in range(2, int(num**0.5) + 1)):
            primes.append(num)
    return primes

result = sieve(30)
print(f"Primes up to 30: {result}")
"""
    output, elapsed_ms = SandboxExecutionEngine.execute_snippet(code)
    assert "Primes up to 30: [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]" in output
    assert elapsed_ms > 0.0
    assert elapsed_ms < 1000.0  # Must complete well within 1 second


def test_banned_import_socket_detection() -> None:
    """Verifies that unauthorized network module imports are blocked statically at AST level."""
    malicious_code = "import socket\ns = socket.socket()"
    with pytest.raises(ASTSecurityViolation) as exc_info:
        SandboxExecutionEngine.execute_snippet(malicious_code)
    assert "Forbidden module import: 'socket'" in str(exc_info.value)


def test_banned_import_subprocess_detection() -> None:
    """Verifies that shell spawning via subprocess is rejected."""
    malicious_code = "from subprocess import Popen\nPopen(['whoami'])"
    with pytest.raises(ASTSecurityViolation) as exc_info:
        SandboxExecutionEngine.execute_snippet(malicious_code)
    assert "Forbidden from-import: 'subprocess'" in str(exc_info.value)


def test_banned_builtin_eval_detection() -> None:
    """Verifies that dynamic meta-programming primitives (eval/exec) are blocked."""
    payload = "payload = '2 + 2'\nx = eval(payload)"
    with pytest.raises(ASTSecurityViolation) as exc_info:
        SandboxExecutionEngine.execute_snippet(payload)
    assert "Forbidden direct builtin call: 'eval'" in str(exc_info.value)


def test_banned_dangerous_attribute_access() -> None:
    """Verifies that dangerous methods like os.system or os.remove are rejected."""
    payload = "class Dummy:\n    def system(self): pass\nd = Dummy()\nd.system()"
    with pytest.raises(ASTSecurityViolation) as exc_info:
        SandboxExecutionEngine.execute_snippet(payload)
    assert "Forbidden dangerous method call: 'system'" in str(exc_info.value)


def test_syntax_error_handling() -> None:
    """Verifies that broken Python syntax reports a clean security exception."""
    broken_code = "def invalid_syntax(:\n    return 42"
    with pytest.raises(ASTSecurityViolation) as exc_info:
        SandboxExecutionEngine.execute_snippet(broken_code)
    assert "Syntax error" in str(exc_info.value)


def test_tool_invocation_wrapper_success() -> None:
    """Tests the MCP protocol tool handler entry point for success response format."""
    args = {"code": "x = sum([10, 20, 30])\nprint(f'Total: {x}')"}
    result = handle_sandbox_invocation(args)
    assert not result.isError
    assert len(result.content) == 1
    assert "AST Sandbox Status: PASSED" in result.content[0]["text"]
    assert "Total: 60" in result.content[0]["text"]


def test_tool_invocation_wrapper_security_rejection() -> None:
    """Tests the MCP protocol tool handler entry point for security violation handling."""
    args = {"code": "import requests\nr = requests.get('https://example.com')"}
    result = handle_sandbox_invocation(args)
    assert result.isError
    assert "Security Policy Rejected" in result.content[0]["text"]
    assert "Forbidden module import: 'requests'" in result.content[0]["text"]


if __name__ == "__main__":
    pytest.main(["-v", __file__])
