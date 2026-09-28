"""
Deterministic Unit-Test Harness for NexusMCP Web Dashboard & Telemetry Engine
Verifies HTML rendering, telemetry state tracking, and live simulation APIs.
"""

import sys
from pathlib import Path

# Add src to pythonpath
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from dashboard import get_dashboard_html, TelemetryTracker


def test_dashboard_html_generation() -> None:
    """Verifies that the dashboard HTML generates completely with all cyber-security components."""
    html = get_dashboard_html()
    assert isinstance(html, str)
    assert len(html) > 5000
    assert "<!DOCTYPE html>" in html
    assert "NexusMCP Gateway" in html
    assert "Live Security Intercept Ledger" in html
    assert "Interactive Threat & Tool Simulator" in html
    assert "execute_python_sandbox" in html or "AST Sandbox" in html
    assert "safe_sql_query" in html or "Safe SQL" in html
    assert "calculate_model_route" in html or "Cost Router" in html


def test_telemetry_tracker_initial_state() -> None:
    """Verifies default metrics and recent event seeding in TelemetryTracker."""
    tracker = TelemetryTracker()
    stats = tracker.get_stats()
    assert stats["total_requests"] >= 1000
    assert stats["blocked_threats"] > 0
    assert stats["allowed_queries"] > 0
    assert stats["defense_rate_pct"] == 100.0
    assert len(stats["recent_events"]) >= 4


def test_telemetry_event_recording_blocked() -> None:
    """Verifies that recording a blocked event increments the threat counter."""
    tracker = TelemetryTracker()
    initial_blocked = tracker.blocked_threats
    initial_total = tracker.total_requests

    tracker.record_event(
        tool="safe_sql_query",
        event_type="MUTATION_BLOCKED",
        status="BLOCKED",
        message="DROP TABLE test_table",
        reason="Blocked by circuit breaker",
        latency_ms=0.08
    )

    stats = tracker.get_stats()
    assert stats["blocked_threats"] == initial_blocked + 1
    assert stats["total_requests"] == initial_total + 1
    assert stats["recent_events"][0]["status"] == "BLOCKED"
    assert stats["recent_events"][0]["badge_class"] == "badge-danger"


def test_telemetry_event_recording_allowed() -> None:
    """Verifies that recording an allowed query increments the allowed queries counter."""
    tracker = TelemetryTracker()
    initial_allowed = tracker.allowed_queries

    tracker.record_event(
        tool="safe_sql_query",
        event_type="READ_AUTHORIZED",
        status="ALLOWED",
        message="SELECT * FROM settings",
        reason="Query executed safely",
        latency_ms=0.05
    )

    stats = tracker.get_stats()
    assert stats["allowed_queries"] == initial_allowed + 1
    assert stats["recent_events"][0]["status"] == "ALLOWED"
    assert stats["recent_events"][0]["badge_class"] == "badge-success"


if __name__ == "__main__":
    test_dashboard_html_generation()
    test_telemetry_tracker_initial_state()
    test_telemetry_event_recording_blocked()
    test_telemetry_event_recording_allowed()
    print("All dashboard verification tests passed!")
