FROM python:3.11-slim

WORKDIR /app

# Install uv (cached unless base image changes)
RUN pip install uv

# Copy dependency files first for layer caching
# Dependencies only re-install when pyproject.toml or uv.lock change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code (changes frequently, but deps layer is cached)
COPY alembic.ini ./
COPY migrations/ migrations/
COPY app/ app/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
