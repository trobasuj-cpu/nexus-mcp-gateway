# Multi-stage hardened non-root container for NexusMCP Gateway
FROM python:3.13-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.13-slim AS runner

WORKDIR /app

# Hardening: Run as unprivileged non-root user (UID 10001)
RUN groupadd -g 10001 mcpuser && \
    useradd -u 10001 -g mcpuser -m -s /bin/bash mcpuser

COPY --from=builder /root/.local /home/mcpuser/.local
COPY --chown=mcpuser:mcpuser src/ ./src/
COPY --chown=mcpuser:mcpuser run_tests.py .

ENV PATH=/home/mcpuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NEXUS_MCP_PORT=8080

USER mcpuser

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["python", "src/server.py"]
