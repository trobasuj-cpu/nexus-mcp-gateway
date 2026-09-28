"""
Zero-Dependency Standalone Test Runner for NexusMCP
Executes all unit tests and security benchmarks using pure Python 3 standard library.
Ensures 100% deterministic test execution in offline / air-gapped environments.
"""

from __future__ import annotations
import sys
import time
from pathlib import Path

# Add src to sys.path
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
TESTS_DIR = BASE_DIR / "tests"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(TESTS_DIR))

import test_ast_sandbox
import test_safe_sql
import test_mcp_protocol
import test_dashboard
import test_server_live


def run_all() -> bool:
    print("=" * 70)
    print("NexusMCP Deterministic Verification Test Runner (Python Standard Lib)")
    print(f"Target: {SRC_DIR}")
    print("=" * 70)

    test_modules = [
        ("AST Sandbox Security", test_ast_sandbox),
        ("Safe SQL Engine", test_safe_sql),
        ("MCP Protocol 2026", test_mcp_protocol),
        ("Web Dashboard & Telemetry", test_dashboard),
        ("Live HTTP Daemon & Simulator", test_server_live)
    ]

    total_passed = 0
    total_failed = 0
    start_all = time.perf_counter()

    for module_name, mod in test_modules:
        print(f"\n[SUITE] Running {module_name}...")
        test_funcs = [getattr(mod, f) for f in dir(mod) if f.startswith("test_") and callable(getattr(mod, f))]

        for func in test_funcs:
            test_name = func.__name__
            t0 = time.perf_counter()
            try:
                func()
                elapsed = (time.perf_counter() - t0) * 1000.0
                print(f"  [PASS] {test_name:<45} [{elapsed:>6.2f} ms]")
                total_passed += 1
            except Exception as err:
                elapsed = (time.perf_counter() - t0) * 1000.0
                print(f"  [FAIL] {test_name:<45} [{elapsed:>6.2f} ms] -> {err}")
                total_failed += 1

    total_duration = (time.perf_counter() - start_all) * 1000.0
    print("\n" + "=" * 70)
    print(f"TEST RUN SUMMARY: {total_passed} passed, {total_failed} failed in {total_duration:.2f} ms")
    if total_failed == 0:
        print("ALL VERIFICATION SUITES DETERMINISTICALLY PASSED! (Zero Defects)")
        print("=" * 70)
        return True
    else:
        print("FAILURES DETECTED! Review outputs above.")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
