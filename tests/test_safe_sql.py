"""
Deterministic Unit-Test Harness for Safe SQL Query Engine
Validates read-only safeguards, destructive query blocks, and Markdown table output.
Part of NexusMCP Pillar 2: Deterministic Verification Harness.
"""

import pytest
import sys
from pathlib import Path

# Add src to pythonpath
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from tools.safe_sql import (
    SQLSafetyValidator,
    SQLSecurityViolation,
    SQLiteSafeRunner,
    handle_sql_invocation
)


def test_valid_select_query_execution() -> None:
    """Verifies that legitimate SELECT statements execute and return columns and rows."""
    runner = SQLiteSafeRunner(db_path=":memory:")
    cols, rows, count, elapsed_ms = runner.execute_query(
        "SELECT host, cpu_pct, status FROM system_metrics ORDER BY cpu_pct ASC;"
    )
    assert cols == ["host", "cpu_pct", "status"]
    assert len(rows) == 3
    assert count == 3
    assert rows[0][0] == "node-ap-south-1"
    assert rows[0][1] == 12.0
    assert elapsed_ms > 0.0


def test_destructive_drop_table_blocked() -> None:
    """Verifies that DROP TABLE queries are blocked unconditionally regardless of flags."""
    with pytest.raises(SQLSecurityViolation) as exc_info:
        SQLSafetyValidator.analyze_statement("DROP TABLE system_metrics;", allow_mutation=True)
    assert "Unconditional Security Block" in str(exc_info.value)
    assert "'DROP'" in str(exc_info.value)


def test_destructive_truncate_blocked() -> None:
    """Verifies that TRUNCATE statements are unconditionally intercepted."""
    with pytest.raises(SQLSecurityViolation) as exc_info:
        SQLSafetyValidator.analyze_statement("TRUNCATE TABLE audit_logs;", allow_mutation=True)
    assert "Unconditional Security Block" in str(exc_info.value)
    assert "'TRUNCATE'" in str(exc_info.value)


def test_unbounded_delete_without_where_blocked() -> None:
    """Verifies that DELETE queries without WHERE clauses are rejected to prevent mass wiping."""
    with pytest.raises(SQLSecurityViolation) as exc_info:
        SQLSafetyValidator.analyze_statement("DELETE FROM system_metrics;", allow_mutation=True)
    assert "Unbounded Mutation Detected" in str(exc_info.value)


def test_read_only_mode_blocks_insert() -> None:
    """Verifies that data-modifying queries are rejected when allow_mutation is False."""
    with pytest.raises(SQLSecurityViolation) as exc_info:
        SQLSafetyValidator.analyze_statement(
            "INSERT INTO system_metrics (host, cpu_pct, status) VALUES ('node-test', 50.0, 'OK');",
            allow_mutation=False
        )
    assert "Mutation Denied" in str(exc_info.value)
    assert "Read-Only mode" in str(exc_info.value)


def test_authorized_mutation_succeeds() -> None:
    """Verifies that legitimate parameterized mutations succeed when explicitly allowed."""
    runner = SQLiteSafeRunner(db_path=":memory:")
    insert_sql = "INSERT INTO system_metrics (host, cpu_pct, status) VALUES ('node-us-west-2', 33.3, 'HEALTHY');"
    cols, rows, count, elapsed_ms = runner.execute_query(insert_sql, allow_mutation=True)
    assert count == 1

    # Verify data persisted
    check_cols, check_rows, _, _ = runner.execute_query("SELECT host FROM system_metrics WHERE host = 'node-us-west-2';")
    assert len(check_rows) == 1
    assert check_rows[0][0] == "node-us-west-2"


def test_sql_tool_wrapper_success() -> None:
    """Tests the MCP protocol tool handler entry point for SQL query execution."""
    args = {"query": "SELECT host, status FROM system_metrics WHERE cpu_pct < 50.0;"}
    result = handle_sql_invocation(args)
    assert not result.isError
    assert len(result.content) == 1
    text = result.content[0]["text"]
    assert "[SQL Safe Engine: OK]" in text
    assert "node-us-east-1" in text
    assert "node-ap-south-1" in text


def test_sql_tool_wrapper_error() -> None:
    """Tests the MCP protocol tool handler entry point for security rejection formatting."""
    args = {"query": "ALTER TABLE system_metrics ADD COLUMN secret TEXT;"}
    result = handle_sql_invocation(args)
    assert result.isError
    assert "SQL Guardrail Blocked" in result.content[0]["text"]


if __name__ == "__main__":
    pytest.main(["-v", __file__])
