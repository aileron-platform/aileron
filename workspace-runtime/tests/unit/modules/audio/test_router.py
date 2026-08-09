from __future__ import annotations

from app.main import app
from app.modules.audio.router import get_audio_transcription_service


class FakeAudioTranscriptionService:
    def __init__(self) -> None:
        self.filename: str | None = None
        self.content_type: str | None = None

    async def transcribe(self, file) -> str:
        self.filename = file.filename
        self.content_type = file.content_type
        return "hello from voice"


def test_transcribes_audio_at_audio_route(client) -> None:
    service = FakeAudioTranscriptionService()
    app.dependency_overrides[get_audio_transcription_service] = lambda: service
    try:
        response = client.post(
            "/api/v1/audio/transcriptions",
            files={"file": ("voice.webm", b"voice-bytes", "audio/webm")},
        )
    finally:
        app.dependency_overrides.pop(get_audio_transcription_service, None)

    assert response.status_code == 200
    assert response.json() == {"text": "hello from voice"}
    assert service.filename == "voice.webm"
    assert service.content_type == "audio/webm"


def test_thread_scoped_transcription_route_fails_closed(client) -> None:
    response = client.post(
        "/api/v1/threads/audio/transcriptions",
        files={"file": ("voice.webm", b"voice-bytes", "audio/webm")},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["errorCode"] == (
        "WORKSPACE_RUNTIME_ACTION_FORBIDDEN"
    )
