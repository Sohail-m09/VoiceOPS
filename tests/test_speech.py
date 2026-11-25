
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from voiceops.services.speech import transcribe_audio


async def test_transcribe_audio_returns_transcript():
    generate_content = AsyncMock(
        return_value=SimpleNamespace(
            text="Check stock for product P-101."
        )
    )

    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=generate_content,
            )
        )
    )

    transcript = await transcribe_audio(
        b"sample-wav-data",
        "audio/wav",
        client=client,
        model="test-model",
    )

    assert transcript == "Check stock for product P-101."

    generate_content.assert_awaited_once()

    call = generate_content.await_args

    assert call.kwargs["model"] == "test-model"
    assert call.kwargs["contents"][0].inline_data.data == b"sample-wav-data"
    assert call.kwargs["contents"][0].inline_data.mime_type == "audio/wav"


async def test_transcribe_audio_rejects_empty_audio():
    with pytest.raises(ValueError, match="cannot be empty"):
        await transcribe_audio(
            b"",
            "audio/wav",
            client=SimpleNamespace(),
        )


async def test_transcribe_audio_rejects_unsupported_format():
    with pytest.raises(ValueError, match="Only WAV"):
        await transcribe_audio(
            b"sample-audio",
            "audio/mp3",
            client=SimpleNamespace(),
        )


async def test_transcribe_audio_rejects_empty_gemini_response():
    generate_content = AsyncMock(
        return_value=SimpleNamespace(text="  ")
    )

    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=generate_content,
            )
        )
    )

    with pytest.raises(RuntimeError, match="empty transcription"):
        await transcribe_audio(
            b"sample-wav-data",
            "audio/wav",
            client=client,
        )
