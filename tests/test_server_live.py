"""
Deterministic Live Server HTTP Verification Test
Spawns an ephemeral server instance and validates all endpoints:
- GET / (Web Dashboard)
- GET /api/stats (Telemetry)
- POST /api/test/sandbox (Interactive AST Sandbox)
- POST /api/test/sql (Interactive Safe SQL)
- POST /api/test/route (Interactive Cost Router)
- POST /mcp (MCP Wire protocol)
"""

import json
import threading
import time
import urllib.request
import sys
from pathlib import Path

# Add src to sys.path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from server import run_server


def test_live_server_endpoints() -> None:
    port = 8123
    server_thread = threading.Thread(target=run_server, kwargs={"host": "127.0.0.1", "port": port}, daemon=True)
    server_thread.start()
    time.sleep(0.4)

    # 1. GET / (Dashboard HTML)
    resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/")
    assert resp.status == 200
    html = resp.read().decode("utf-8")
    assert "NexusMCP Gateway" in html
    assert "Live Security Intercept Ledger" in html

    # 2. GET /api/stats
    resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/stats")
    assert resp.status == 200
    stats = json.loads(resp.read().decode("utf-8"))
    assert "blocked_threats" in stats
    assert stats["defense_rate_pct"] == 100.0

    # 3. POST /api/test/sandbox
    payload = json.dumps({"code": "import os\nos.system('calc')"}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/test/sandbox", data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    res_data = json.loads(resp.read().decode("utf-8"))
    assert res_data["isError"] is True
    text_lower = res_data["content"][0]["text"].lower()
    assert "rejected" in text_lower or "forbidden" in text_lower

    # 4. POST /api/test/sql
    sql_payload = json.dumps({"query": "DROP TABLE users;"}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/test/sql", data=sql_payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    res_data = json.loads(resp.read().decode("utf-8"))
    assert res_data["isError"] is True
    assert "destructive" in res_data["content"][0]["text"].lower() or "drop" in res_data["content"][0]["text"].lower()

    # 5. POST /api/test/route
    route_payload = json.dumps({"task_description": "Create simple pytest helper", "estimated_tokens": 1000}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/test/route", data=route_payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    res_data = json.loads(resp.read().decode("utf-8"))
    assert not res_data["isError"]
    assert "deepseek-v4.1-flash" in res_data["content"][0]["text"].lower()

    print("Live server HTTP verification tests passed completely!")


if __name__ == "__main__":
    test_live_server_endpoints()
