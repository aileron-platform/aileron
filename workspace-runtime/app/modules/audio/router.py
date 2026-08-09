from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse

from app.middleware.auth import get_current_user_id
from app.modules.audio.transcription import (
    AudioTranscriptionError,
    AudioTranscriptionService,
)

router = APIRouter(tags=["Audio"])


def get_audio_transcription_service() -> AudioTranscriptionService:
    return AudioTranscriptionService()


@router.post("/audio/transcriptions", response_model=None)
async def transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
    service: AudioTranscriptionService = Depends(get_audio_transcription_service),
) -> dict[str, str] | JSONResponse:
    get_current_user_id(request)
    try:
        text = await service.transcribe(file)
    except AudioTranscriptionError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "error_info": exc.error_info or {},
            },
        )
    return {"text": text}
