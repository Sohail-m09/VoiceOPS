import logging

from fastapi import FastAPI
from pydantic import BaseModel

from voiceops import __version__
from voiceops.config import get_settings
from voiceops.logging_config import configure_logging

configure_logging(get_settings().log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="VoiceOps",
    description="Voice-enabled Agentic AI for Warehouse and Supply Chain Operations",
    version=__version__,
)


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


@app.get("/health")
async def health() -> HealthResponse:
    logger.debug("Health check requested")
    settings = get_settings()
    return HealthResponse(status="ok", version=__version__, environment=settings.app_env)
