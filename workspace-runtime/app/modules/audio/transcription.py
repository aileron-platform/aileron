from __future__ import annotations

import os

import httpx
from fastapi import UploadFile, status


SUPPORTED_AUDIO_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/ogg",
}
MAX_AUDIO_BYTES = 25 * 1024 * 1024


class AudioTranscriptionError(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        error_info: dict[str, object] | None = None,
    ) -> None:
        super().__init__(error_code)
        self.status_code = status_code
        self.error_code = error_code
        self.error_info = error_info or {}


class AudioTranscriptionService:
    async def transcribe(self, file: UploadFile) -> str:
        content_type = (file.content_type or "").split(";")[0].strip().lower()
        if content_type not in SUPPORTED_AUDIO_TYPES:
            raise AudioTranscriptionError(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "unsupported_audio_type",
                {"contentType": file.content_type},
            )

        audio = await file.read()
        if len(audio) > MAX_AUDIO_BYTES:
            raise AudioTranscriptionError(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                "audio_too_large",
                {"maxBytes": MAX_AUDIO_BYTES},
            )

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise AudioTranscriptionError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "transcription_unavailable",
                {},
            )

        model = os.environ.get("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")
        filename = file.filename or "voice.webm"
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    data={"model": model},
                    files={"file": (filename, audio, content_type)},
                )
        except httpx.HTTPError as exc:
            raise AudioTranscriptionError(
                status.HTTP_502_BAD_GATEWAY,
                "transcription_failed",
                {"reason": str(exc)},
            ) from exc

        if response.status_code >= 400:
            raise AudioTranscriptionError(
                status.HTTP_502_BAD_GATEWAY,
                "transcription_failed",
                {"upstreamStatus": response.status_code},
            )

        payload = response.json()
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str):
            raise AudioTranscriptionError(
                status.HTTP_502_BAD_GATEWAY,
                "transcription_failed",
                {"reason": "missing_text"},
            )
        return text
