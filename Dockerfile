FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --upgrade pip && pip install uv
COPY pyproject.toml .
RUN uv pip install --system .
COPY . .

# PM-Labs fork guard: fail the build if an upstream sync (or a manual conflict
# resolution) drops the static refresh-token auth from ads_mcp/utils.py.
# scripts/sync.sh rolls back on a failed build, so a broken-auth server can't
# deploy silently again (2026-10-02 incident -- see tests/pm_static_auth_test.py).
RUN python -m unittest tests.pm_static_auth_test

ENV PORT=8080
ENV BACKEND_PORT=8081
EXPOSE 8080

RUN chmod +x start.sh
CMD ["./start.sh"]
