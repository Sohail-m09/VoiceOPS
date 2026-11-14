FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install dependencies first so Docker can cache this layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

# Then add the application code and install the project itself.
COPY src ./src
RUN uv sync --locked --no-dev

RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "voiceops.main:app", "--host", "0.0.0.0", "--port", "8000"]