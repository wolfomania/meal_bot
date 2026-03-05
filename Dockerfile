# syntax=docker/dockerfile:1.7

# --- Build stage: install dependencies with uv ---
FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached unless lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --no-editable

# Copy source and install the project itself
COPY meal_bot/ meal_bot/
RUN uv sync --frozen --no-dev --no-editable

# --- Runtime stage: slim image without uv or build tools ---
FROM python:3.13-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg tini \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app \
    && useradd --system --gid app --create-home --home-dir /home/app app

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Copy application source
COPY --chown=app:app meal_bot/ meal_bot/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app

ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "meal_bot.main"]
