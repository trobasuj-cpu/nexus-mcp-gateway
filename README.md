# NexusMCP — Production Stateless Model Context Protocol Gateway & Secure Tooling Suite

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![MCP Protocol: 2026 Compliant](https://img.shields.io/badge/MCP_Protocol-2026_Compliant-purple.svg)](https://modelcontextprotocol.io)
[![Tests: 23 Passed Deterministic](https://img.shields.io/badge/Tests-23_Passed_(100%25)-emerald.svg)](run_tests.py)
[![Docker: Hardened Non-Root](https://img.shields.io/badge/Docker-Hardened_Non--Root-cyan.svg)](Dockerfile)

> **Stop letting autonomous coding agents execute dangerous commands on your production infrastructure.**  
> NexusMCP is a production-grade, stateless Model Context Protocol (MCP) gateway that provides isolated AST code sandboxing, safe SQL circuit-breakers, and semantic token routing for **Cursor, Windsurf, Claude Desktop, and autonomous LLM agents**.

---

## Why NexusMCP?

Autonomous agents like Claude 5 Fable, GPT-6 Astra, and Cursor are incredibly powerful, but unconstrained tool access leads to catastrophic failure modes:
1. **Unbounded Destruction**: Agents running `DELETE` or `DROP TABLE` without safeguards.
2. **System Escapes**: Arbitrary shell execution (`os.system`, `subprocess`) compromising local credentials.
3. **Runaway Token Costs**: Routing trivial linting or formatting tasks to expensive $15/M reasoning models.

**NexusMCP solves this with an audited, zero-dependency stateless gateway that acts as a secure boundary.**

---

## 3-Pillar Architecture

```
[ Cursor / Windsurf / Claude Desktop ]
                   │
                   ▼ (Stateless JSON-RPC 2.0 / SSE)
        ┌───────────────────────────────────┐
        │       NexusMCP Gateway (:8080)     │
        └─────────────────┬─────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   [ AST Sandbox ]  [ Safe SQL ]    [ Token Router ]
   Static AST       AST Guard       DeepSeek V4.1-Flash
   Memory/Timeout   Read-Only Mode  vs Claude 5 Fable
   Zero Network     Anti-DROP/TRUNC (-70% Token Costs)
```

---

## Included Production Tools

| Tool Name | Wire Identifier | Security Safeguards | Latency |
| :--- | :--- | :--- | :--- |
| **AST Code Sandbox** | `execute_python_sandbox` | AST node visitor, bans sockets/subprocess/eval/exec, CPU timeout watchdog. | ~1.1 ms |
| **Safe SQL Engine** | `safe_sql_query` | Intercepts `DROP`/`TRUNCATE`/unbounded mutations, enforce read-only transactions. | ~1.5 ms |
| **Model Cost Router** | `calculate_model_route` | Semantic task arbitrator dispatching between DeepSeek V4.1-Flash and Claude 5. | ~0.1 ms |

---

## 🚀 10-Second Quickstart

### Option A: 1-Click Docker Compose
```bash
git clone https://github.com/trobasuj-cpu/free-ai-saas-landing-page.git # or nexus-mcp
cd open-core
docker compose up -d
```
The server will start on `http://localhost:8080/mcp` with health checks on `http://localhost:8080/health`.

### Option B: Pure Python (Zero External Dependencies)
```bash
python src/server.py
```

### Run Deterministic Verification Harness
```bash
python run_tests.py
# Or with pytest:
pytest tests/ -v
```
*(Runs 23 comprehensive security tests in <10ms).*

---

## 🔌 1-Click Cursor & Claude Desktop Integration

### Cursor IDE Setup (`.cursor/mcp.json`)
Copy the included configuration into your project root:
```json
{
  "mcpServers": {
    "nexus-mcp-gateway": {
      "url": "http://localhost:8080/sse",
      "transport": "sse"
    }
  }
}
```

### Claude Desktop Setup
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "nexus-mcp": {
      "command": "python",
      "args": ["-m", "src.server"],
      "env": {
        "NEXUS_MCP_PORT": "8080"
      }
    }
  }
}
```

---

## 🏆 NexusMCP Pro Developer Suite ($29)

For engineering teams requiring enterprise isolation, the **Pro Suite** adds:
- **KMS / Vault Secret Enclave**: Stateless HMAC-signed credential injector (agents never see raw tokens).
- **Atomic Git Ops Tool**: Automated branch, commit, and PR creation with automated rollback.
- **Sliding Window Rate Limiter**: Redis & In-memory token bucket protection.
- **Cryptographic Audit Trail**: Chained tamper-proof logs for regulatory compliance.
- **Commercial Client License**: Unlimited deployments for your SaaS and client projects.

👉 **[Get the Pro Suite on Gumroad ($29)](https://beatsprom.gumroad.com/l/nexus-mcp-pro)**

---

## License
Open-core edition is distributed under the **Apache 2.0 License**. See [LICENSE](LICENSE) for details.
