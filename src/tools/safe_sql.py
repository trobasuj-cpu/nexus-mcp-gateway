"""
Safe SQL Query Engine & Mutation Circuit-Breaker for MCP Agents
Provides controlled relational database execution with strict statement classification,
destructive mutation guards, and LLM context window protection limits.
"""

from __future__ import annotations
import re
import sqlite3
import time
from typing import Dict, Any, List, Optional, Tuple
try:
    from ..protocol import ToolDefinition, ToolParameterSchema, ToolExecutionResult
except (ImportError, ValueError):
    from protocol import ToolDefinition, ToolParameterSchema, ToolExecutionResult


class SQLSecurityViolation(Exception):
    """Raised when an agent attempts a forbidden destructive query without authorization."""
    pass


class SQLSafetyValidator:
    """Performs static parsing and semantic classification of raw SQL statements."""

    DESTRUCTIVE_KEYWORDS: List[str] = [
        "DROP", "TRUNCATE", "ALTER", "GRANT", "REVOKE", "VACUUM", "ATTACH", "DETACH"
    ]

    UNBOUNDED_MUTATION_REGEX = re.compile(
        r"^\s*(DELETE\s+FROM|UPDATE)\s+([a-zA-Z0-9_]+)(?!\s+WHERE\b)",
        re.IGNORECASE | re.MULTILINE
    )

    @classmethod
    def analyze_statement(cls, sql_text: str, allow_mutation: bool) -> Tuple[str, bool]:
        clean_sql = sql_text.strip()
        if not clean_sql:
            raise SQLSecurityViolation("SQL query string is empty.")

        # Normalize comments
        stripped_sql = re.sub(r"--.*?$|/\*.*?\*/", "", clean_sql, flags=re.MULTILINE | re.DOTALL).strip()
        first_word = stripped_sql.split()[0].upper() if stripped_sql else ""

        # Unconditional block for catastrophic DDL
        for bad_kw in cls.DESTRUCTIVE_KEYWORDS:
            if re.search(r"\b" + bad_kw + r"\b", stripped_sql, re.IGNORECASE):
                raise SQLSecurityViolation(f"Unconditional Security Block: '{bad_kw}' operations are strictly forbidden in agent queries.")

        # Check unbounded updates/deletes without WHERE
        if cls.UNBOUNDED_MUTATION_REGEX.search(stripped_sql):
            raise SQLSecurityViolation("Unbounded Mutation Detected: UPDATE or DELETE without explicit WHERE clause is prohibited.")

        # Read-only verification
        is_read_only = first_word in ("SELECT", "WITH", "EXPLAIN", "PRAGMA")
        if not is_read_only and not allow_mutation:
            raise SQLSecurityViolation(f"Mutation Denied: Attempted '{first_word}' statement while agent connection is in Read-Only mode.")

        return first_word, is_read_only


class SQLiteSafeRunner:
    """Manages secure in-memory or file-backed SQLite transactions with query limits."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._initialize_seed_if_memory()

    def _initialize_seed_if_memory(self) -> None:
        if self.db_path == ":memory:":
            cursor = self._conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS system_metrics (id INTEGER PRIMARY KEY, host TEXT, cpu_pct REAL, status TEXT);")
            cursor.execute("INSERT INTO system_metrics (host, cpu_pct, status) VALUES ('node-us-east-1', 42.1, 'HEALTHY'), ('node-eu-central-1', 78.4, 'WARNING'), ('node-ap-south-1', 12.0, 'HEALTHY');")
            self._conn.commit()

    def execute_query(self, sql_query: str, allow_mutation: bool = False, max_rows: int = 100) -> Tuple[List[str], List[List[Any]], int, float]:
        statement_type, is_read_only = SQLSafetyValidator.analyze_statement(sql_query, allow_mutation)

        start_time = time.perf_counter()
        cursor = self._conn.cursor()
        cursor.execute(sql_query)

        if is_read_only and cursor.description:
            columns = [desc[0] for desc in cursor.description]
            rows = [list(r) for r in cursor.fetchmany(max_rows)]
            total_affected = len(rows)
        else:
            columns = ["status"]
            total_affected = cursor.rowcount
            self._conn.commit()
            rows = [["Rows affected: " + str(total_affected)]]

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return columns, rows, total_affected, elapsed_ms


_GLOBAL_RUNNER = SQLiteSafeRunner()


def get_safe_sql_tool_definition() -> ToolDefinition:
    """Exposes tool metadata to MCP protocol engine."""
    return ToolDefinition(
        name="safe_sql_query",
        description="Executes audited SQL queries against relational databases with automated guardrails against destructive DROP/TRUNCATE and unbounded mutations.",
        inputSchema=ToolParameterSchema(
            type="object",
            properties={
                "query": {
                    "type": "string",
                    "description": "SQL statement to validate and execute."
                },
                "allow_mutation": {
                    "type": "boolean",
                    "description": "Explicit opt-in required to perform INSERT, UPDATE, or schema modifications (default: false)."
                },
                "max_rows": {
                    "type": "integer",
                    "description": "Upper bound on rows returned to prevent LLM context overflow (default: 100, max: 500)."
                }
            },
            required=["query"]
        )
    )


def handle_sql_invocation(arguments: Dict[str, Any]) -> ToolExecutionResult:
    """Entry point for executing the SQL tool from an MCP client request."""
    query = arguments.get("query")
    if not query or not isinstance(query, str):
        return ToolExecutionResult.failure("Missing or invalid 'query' parameter.")

    allow_mutation = bool(arguments.get("allow_mutation", False))
    max_rows = min(int(arguments.get("max_rows", 100)), 500)

    try:
        cols, rows, count, elapsed_ms = _GLOBAL_RUNNER.execute_query(
            sql_query=query,
            allow_mutation=allow_mutation,
            max_rows=max_rows
        )
        # Format markdown tabular output
        header = " | ".join(cols)
        divider = " | ".join(["---"] * len(cols))
        rendered_rows = [" | ".join(str(cell) for cell in r) for r in rows]
        table_str = f"{header}\n{divider}\n" + "\n".join(rendered_rows) if rows else "<Empty result set>"

        summary = f"[SQL Safe Engine: OK]\nLatency: {elapsed_ms:.2f}ms | Rows: {count}\n\n{table_str}"
        return ToolExecutionResult.success(summary)
    except SQLSecurityViolation as sec_err:
        return ToolExecutionResult.failure(f"SQL Guardrail Blocked: {sec_err}")
    except Exception as runtime_err:
        return ToolExecutionResult.failure(f"Database Execution Error: {type(runtime_err).__name__}: {runtime_err}")
