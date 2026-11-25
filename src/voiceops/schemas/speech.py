
from pydantic import BaseModel, ConfigDict, Field


class SpeechTranscriptionResponse(BaseModel):
    """Response returned after speech transcription."""

    model_config = ConfigDict(extra="forbid")

    transcript: str = Field(min_length=1)
