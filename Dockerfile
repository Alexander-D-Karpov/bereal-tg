FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY .python-version .

RUN uv sync --frozen --no-dev

COPY bot/ ./bot/

RUN mkdir -p data

CMD ["uv", "run", "python", "-m", "bot.main"]