from fastapi import FastAPI

from voiceops import __version__

app = FastAPI(
    title="VoiceOps",
    description="Voice-enabled Agentic AI for Warehouse and Supply Chain Operations",
    version=__version__,
)
