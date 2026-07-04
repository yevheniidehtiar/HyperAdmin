FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ ./src/
COPY examples/erp/ ./examples/erp/

# Install the project and all extras. The `loadtest` extra brings in asyncpg, so the app can
# talk to PostgreSQL via DATABASE_URL=postgresql://... (db.py normalises it to +asyncpg).
# With no DATABASE_URL set, the app falls back to sqlite+aiosqlite:///erp.db.
RUN uv sync --all-extras

# Expose the port
EXPOSE 8000

# Run the app. Override CMD for multi-worker load testing, e.g.:
#   uv run uvicorn examples.erp.main:app --host 0.0.0.0 --port 8000 --workers 3
CMD ["uv", "run", "fastapi", "dev", "examples/erp/main.py", "--host", "0.0.0.0"]
