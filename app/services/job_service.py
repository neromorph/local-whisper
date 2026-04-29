"""
Job management service for URL-based transcription.
Provides in-memory job tracking, background pipeline execution,
progress updates, cancellation, and automatic cleanup.
"""

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from app import config
from app.services import url_service, whisper_service
from app.utils.files import cleanup_temp
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Job:
    """Represents a transcription job."""
    job_id: str
    url: str
    model: str
    language: str
    task: str
    state: str = "queued"  # see STATE_* constants
    progress: int = 0
    message: str = "Waiting to start"
    result: Optional[dict] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    temp_files: list[Path] = field(default_factory=list)

    def to_status_dict(self) -> dict:
        """Serialize job state for the status API."""
        status = {
            "job_id": self.job_id,
            "state": self.state,
            "progress": self.progress,
            "message": self.message,
            "success": self.state == "completed",
        }
        if self.metadata:
            status["metadata"] = self.metadata
        if self.state == "completed" and self.result:
            status["result"] = self.result
        if self.state == "error" and self.error:
            status["error"] = self.error
        return status


# Job states
STATE_QUEUED = "queued"
STATE_VALIDATING = "validating"
STATE_FETCHING_INFO = "fetching_info"
STATE_DOWNLOADING = "downloading"
STATE_EXTRACTING = "extracting"
STATE_LOADING_MODEL = "loading_model"
STATE_TRANSCRIBING = "transcribing"
STATE_FINALIZING = "finalizing"
STATE_COMPLETED = "completed"
STATE_ERROR = "error"
STATE_CANCELLED = "cancelled"


class CancellationError(Exception):
    """Raised when a job is cancelled by the user."""
    pass


# ---------------------------------------------------------------------------
# Job store (in-memory, thread-safe)
# ---------------------------------------------------------------------------

_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()

# Concurrency semaphore for URL transcription pipelines (threading, not asyncio)
_pipeline_semaphore = threading.Semaphore(config.MAX_CONCURRENT_JOBS)


def create_job(url: str, model: str, language: str, task: str) -> Job:
    """Create a new job and store it."""
    job = Job(
        job_id=str(uuid.uuid4()),
        url=url,
        model=model,
        language=language,
        task=task,
    )
    with _jobs_lock:
        _jobs[job.job_id] = job
    logger.info(f"Created job {job.job_id} for URL transcription")
    return job


def get_job(job_id: str) -> Optional[Job]:
    """Retrieve a job by ID."""
    with _jobs_lock:
        return _jobs.get(job_id)


def cancel_job(job_id: str) -> bool:
    """Request cancellation of a job. Returns True if job was found."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return False
    logger.info(f"Cancellation requested for job {job_id}")
    job.cancel_event.set()
    with _jobs_lock:
        if job.state not in (STATE_COMPLETED, STATE_ERROR, STATE_CANCELLED):
            job.state = STATE_CANCELLED
            job.message = "Cancelling..."
    return True


def _cleanup_job(job: Job) -> None:
    """Delete all temp files associated with a job."""
    for temp_path in job.temp_files:
        cleanup_temp(temp_path)
    # Also try to clean the output template files that yt-dlp may create
    # (already in temp_files if added, but be safe)
    logger.debug(f"Cleaned up {len(job.temp_files)} temp files for job {job.job_id}")


def _update_job(job: Job, state: str, progress: int, message: str) -> None:
    """Thread-safe job state update."""
    with _jobs_lock:
        job.state = state
        job.progress = progress
        job.message = message
    logger.debug(f"Job {job.job_id}: {state} ({progress}%) — {message}")


def _check_cancelled(job: Job) -> bool:
    """Return True if the job has been cancelled."""
    return job.cancel_event.is_set()


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------

def _run_pipeline(job: Job) -> None:
    """
    Run the full URL transcription pipeline in a background thread.
    This function is designed to be called via asyncio.to_thread.
    """
    # Acquire the concurrency semaphore for the entire pipeline.
    # This prevents unbounded simultaneous downloads + transcriptions.
    acquired = _pipeline_semaphore.acquire(timeout=30)
    if not acquired:
        _update_job(job, STATE_ERROR, 0, "Server is too busy. Please try again later.")
        with _jobs_lock:
            job.error = "Server is too busy. Please try again later."
        return

    audio_path: Optional[Path] = None
    transcription_thread: Optional[threading.Thread] = None

    try:
        # 1. Validating URL
        if _check_cancelled(job):
            raise CancellationError()
        _update_job(job, STATE_VALIDATING, 2, "Validating URL...")
        url_service.validate_url(job.url)

        # 2. Fetching media info
        if _check_cancelled(job):
            raise CancellationError()
        _update_job(job, STATE_FETCHING_INFO, 10, "Fetching media information...")
        metadata = url_service.fetch_metadata(job.url)
        with _jobs_lock:
            job.metadata = metadata.to_dict()
        _update_job(job, STATE_FETCHING_INFO, 14, f"Found: {metadata.title or 'media'}")

        # Limit check: if duration is known and excessive, warn/reject
        if metadata.duration and metadata.duration > 14400:  # 4 hours
            raise RuntimeError(
                f"Media duration ({metadata.duration / 3600:.1f}h) exceeds the 4-hour limit."
            )

        # 3. Downloading audio
        if _check_cancelled(job):
            raise CancellationError()
        _update_job(job, STATE_DOWNLOADING, 20, "Downloading audio...")

        def download_progress(pct: int, msg: str) -> None:
            # Map 0-100 download to 20-55 overall
            if pct >= 0:
                mapped = 20 + int(pct * 0.35)
            else:
                mapped = 20
            _update_job(job, STATE_DOWNLOADING, mapped, msg)

        audio_path = url_service.download_audio(
            job.url,
            config.TEMP_DIR,
            cancel_event=job.cancel_event,
            progress_callback=download_progress,
        )
        with _jobs_lock:
            job.temp_files.append(audio_path)
        _update_job(job, STATE_DOWNLOADING, 55, "Download complete")

        # 4. Extracting (yt-dlp already extracted, this is fast)
        if _check_cancelled(job):
            raise CancellationError()
        _update_job(job, STATE_EXTRACTING, 60, "Preparing audio for transcription...")

        # 5. Loading model
        if _check_cancelled(job):
            raise CancellationError()
        _update_job(job, STATE_LOADING_MODEL, 68, "Loading Whisper model...")
        whisper_service.get_model(job.model)
        _update_job(job, STATE_LOADING_MODEL, 74, "Model ready")

        # 6. Transcribing
        if _check_cancelled(job):
            raise CancellationError()
        _update_job(job, STATE_TRANSCRIBING, 78, "Transcribing audio...")

        transcription_done = threading.Event()
        transcription_result: Optional[dict] = None
        transcription_error: Optional[Exception] = None

        def transcribe_worker() -> None:
            nonlocal transcription_result, transcription_error
            try:
                result = whisper_service.transcribe(
                    audio_path,
                    job.model,
                    job.language,
                    job.task,
                )
                transcription_result = result
            except Exception as exc:
                transcription_error = exc
            finally:
                transcription_done.set()

        transcription_thread = threading.Thread(target=transcribe_worker, daemon=True)
        transcription_thread.start()

        # Slow progress bump while transcribing (78-95)
        progress = 78
        while not transcription_done.is_set():
            if _check_cancelled(job):
                raise CancellationError()
            time.sleep(2)
            if progress < 94:
                progress += 2
                _update_job(job, STATE_TRANSCRIBING, progress, "Transcribing audio...")

        transcription_thread.join(timeout=10)
        transcription_thread = None
        if transcription_error:
            raise transcription_error
        if transcription_result is None:
            raise RuntimeError("Transcription produced no result.")

        # 7. Finalizing
        if _check_cancelled(job):
            raise CancellationError()
        _update_job(job, STATE_FINALIZING, 97, "Finalizing...")

        result = transcription_result
        result["metadata"] = job.metadata or {}

        # 8. Completed — set state, progress, message, and result in a SINGLE lock
        # acquisition to prevent the race where state=completed is visible before result.
        with _jobs_lock:
            job.state = STATE_COMPLETED
            job.progress = 100
            job.message = "Transcription complete!"
            job.result = result
        logger.info(
            f"Job {job.job_id} completed: {len(result.get('text', ''))} chars, "
            f"language={result.get('language', 'unknown')}"
        )

    except CancellationError:
        # Wait briefly for the transcription thread to finish before cleanup
        if transcription_thread and transcription_thread.is_alive():
            transcription_thread.join(timeout=30)
        _update_job(job, STATE_CANCELLED, job.progress, "Cancelled by user.")
        logger.info(f"Job {job.job_id} cancelled")
    except RuntimeError as exc:
        msg = str(exc)
        _update_job(job, STATE_ERROR, job.progress, msg)
        with _jobs_lock:
            job.error = msg
        logger.error(f"Job {job.job_id} error: {msg}")
    except Exception as exc:
        logger.error(f"Job {job.job_id} unexpected error: {exc}")
        _update_job(job, STATE_ERROR, job.progress, f"Transcription failed: {exc}")
        with _jobs_lock:
            job.error = str(exc)
    finally:
        _cleanup_job(job)
        if acquired:
            _pipeline_semaphore.release()


# ---------------------------------------------------------------------------
# Async entry point
# ---------------------------------------------------------------------------

def _on_pipeline_done(task: asyncio.Task) -> None:
    """Catch unexpected failures of the pipeline task itself."""
    exc = task.exception()
    if exc is not None:
        logger.error(f"Pipeline task failed unexpectedly: {exc}")


async def start_job_pipeline(job: Job) -> None:
    """
    Start the pipeline for a job in a background thread.
    Returns immediately (non-blocking).
    """
    task = asyncio.create_task(asyncio.to_thread(_run_pipeline, job))
    task.add_done_callback(_on_pipeline_done)
