# VoiceOPS
Voice-enabled Agentic AI for Warehouse and Supply Chain Operations

## Status
Engineering foundation: project structure, tooling, a FastAPI app with a `/health` endpoint, structured logging, automated tests and Docker.

## Requirements
- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) for dependency management
- Docker Desktop (only needed to run the app in a container)

## Setup (Windows PowerShell)
```powershell
git clone https://github.com/Sohail-m09/VoiceOPS.git
cd VoiceOPS
uv sync --locked
.\.venv\Scripts\Activate.ps1
copy .env.example .env
```
Skip the last line if you already have a `.env`, because it would be overwritten.

## Configuration
Settings are read from environment variables, or from a local `.env` file. `.env` is ignored by Git, so never commit it.

| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | `development` | Name of the running environment, reported by `/health` |
| `LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

## Run locally
```powershell
uvicorn voiceops.main:app --reload
```
Open http://127.0.0.1:8000/docs for the interactive API docs.

## Run with Docker
```powershell
docker compose up --build
docker compose down
```

## API
`GET /health` returns:
```json
{"status": "ok", "version": "0.1.0", "environment": "development"}
```

## Tests and code quality
```powershell
pytest
ruff check .
ruff format --check .
```

## Project layout
```
src/voiceops/
    __init__.py          package and version
    config.py            settings loaded from the environment
    logging_config.py    log format and levels
    main.py              FastAPI app and /health
tests/                   automated tests
.env.example             template for local settings
Dockerfile, docker-compose.yml, .dockerignore
pyproject.toml, uv.lock  dependencies and tool settings
PROJECT_PROGRESS.md      Phase 0 progress log
```