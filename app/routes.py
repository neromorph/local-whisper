"""
FastAPI route definitions.
Provides frontend serving, health checks, transcription (upload + URL), and job management.
"""

import asyncio

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app import config
from app.services import whisper_service, job_service, url_service
from app.utils.files import cleanup_temp, stream_upload_temp, validate_extension
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Concurrency semaphore for CPU-bound transcription jobs (upload mode)
_transcribe_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_JOBS)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class UrlTranscriptionRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048, description="URL of the video/audio to transcribe")
    model: str = Field(default=config.DEFAULT_MODEL, description="Whisper model name")
    language: str = Field(default=config.DEFAULT_LANGUAGE, description="Language code or 'auto'")
    task: str = Field(default=config.DEFAULT_TASK, description="Task: 'transcribe' or 'translate'")


class JobStatusResponse(BaseModel):
    job_id: str
    state: str
    progress: int
    message: str
    success: bool
    metadata: dict | None = None
    result: dict | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Frontend & utilities
# ---------------------------------------------------------------------------

@router.get("/")
async def serve_frontend():
    """Serve the main frontend HTML file."""
    index_path = config.BASE_DIR / "static" / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    Reports backend status, ffmpeg/yt-dlp availability, cached models, and temp dir state.
    """
    ffmpeg_ok = config.FFMPEG_AVAILABLE
    ytdlp_ok = config.YT_DLP_AVAILABLE
    models = whisper_service.get_cached_models()

    status = "ok"
    if not ffmpeg_ok or not ytdlp_ok:
        status = "degraded"
    if not config.WHISPER_BACKEND:
        status = "degraded"

    return {
        "status": status,
        "whisper_backend": config.WHISPER_BACKEND or "none",
        "ffmpeg_available": ffmpeg_ok,
        "yt_dlp_available": ytdlp_ok,
        "models_cached": models,
        "temp_dir_writable": config.TEMP_WRITABLE,
    }


@router.get("/extensions")
async def get_extensions():
    """Return the set of allowed file extensions for upload validation."""
    return {
        "extensions": sorted(config.ALLOWED_EXTENSIONS),
    }


# ---------------------------------------------------------------------------
# Upload transcription (existing, unchanged)
# ---------------------------------------------------------------------------

@router.post("/transcribe")
async def transcribe_endpoint(
    file: UploadFile = File(...),
    model: str = Form(default=config.DEFAULT_MODEL),
    language: str = Form(default=config.DEFAULT_LANGUAGE),
    task: str = Form(default=config.DEFAULT_TASK),
):
    """
    Accept an audio/video file and run whisper transcription.
    Streams the file directly to disk and validates size mid-stream.
    """
    if model not in config.WHISPER_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{model}'. Allowed: {', '.join(config.WHISPER_MODELS)}",
        )

    if task not in config.VALID_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task '{task}'. Allowed: {', '.join(sorted(config.VALID_TASKS))}",
        )

    if language not in config.VALID_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language '{language}'. Use 'auto' or a valid ISO 639-1 code.",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not validate_extension(file.filename):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid file type '{file.filename}'. "
                f"Allowed: {', '.join(sorted(config.ALLOWED_EXTENSIONS))}"
            ),
        )

    temp_path = None
    try:
        temp_path = await stream_upload_temp(file, config.MAX_UPLOAD_BYTES)
        file_size = temp_path.stat().st_size
        logger.info(
            f"Transcribing file: {file.filename} ({file_size} bytes) "
            f"with model={model}, lang={language}, task={task}"
        )

        async with _transcribe_semaphore:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    whisper_service.transcribe,
                    temp_path,
                    model,
                    language,
                    task,
                ),
                timeout=config.MAX_TRANSCRIPTION_SECONDS,
            )

        logger.info(
            f"Transcription complete: {len(result['text'])} chars, "
            f"duration={result['duration']}s"
        )
        return {"success": True, **result}

    except asyncio.TimeoutError:
        logger.error("Transcription timed out")
        raise HTTPException(
            status_code=504,
            detail=(
                f"Transcription exceeded the {config.MAX_TRANSCRIPTION_SECONDS}s timeout. "
                "Try a smaller model or shorter audio file."
            ),
        ) from None
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Transcription error: {exc}")
        detail = str(exc)
        if config.DEBUG:
            import traceback
            detail = traceback.format_exc()
        raise HTTPException(status_code=500, detail=detail) from exc
    finally:
        if temp_path:
            cleanup_temp(temp_path)


# ---------------------------------------------------------------------------
# URL transcription (new)
# ---------------------------------------------------------------------------

def _validate_transcription_inputs(model: str, language: str, task: str) -> None:
    """Shared validation for model, language, and task parameters."""
    if model not in config.WHISPER_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{model}'. Allowed: {', '.join(config.WHISPER_MODELS)}",
        )
    if task not in config.VALID_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task '{task}'. Allowed: {', '.join(sorted(config.VALID_TASKS))}",
        )
    if language not in config.VALID_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language '{language}'. Use 'auto' or a valid ISO 639-1 code.",
        )


@router.post("/transcribe/url")
async def transcribe_url_endpoint(request: UrlTranscriptionRequest):
    """
    Accept a media URL and start a background transcription job.
    Returns immediately with a job_id. Poll /jobs/{job_id}/status for progress.
    """
    # Validate inputs first — gives better UX than "service unavailable" for typos
    _validate_transcription_inputs(request.model, request.language, request.task)

    # Pre-validate URL (lightweight, synchronous)
    try:
        url_service.validate_url(request.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    if not config.YT_DLP_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="yt-dlp is not installed on this server. URL transcription is unavailable.",
        )

    if not config.FFMPEG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ffmpeg is not installed on this server. Transcription is unavailable.",
        )

    if not config.WHISPER_BACKEND:
        raise HTTPException(
            status_code=503,
            detail="No whisper backend is installed. Transcription is unavailable.",
        )

    job = job_service.create_job(
        url=request.url,
        model=request.model,
        language=request.language,
        task=request.task,
    )

    # Start pipeline in background (non-blocking)
    await job_service.start_job_pipeline(job)

    return {"success": True, "job_id": job.job_id}


@router.get("/jobs/{job_id}/status")
async def job_status_endpoint(job_id: str):
    """Get the current status of a transcription job."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_status_dict()


@router.post("/jobs/{job_id}/cancel")
async def job_cancel_endpoint(job_id: str):
    """Request cancellation of a running transcription job."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.state in (job_service.STATE_COMPLETED, job_service.STATE_ERROR):
        return {"success": True, "message": "Job already finished."}

    ok = job_service.cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"success": True, "message": "Cancellation requested."}
