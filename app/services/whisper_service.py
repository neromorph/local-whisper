"""
Whisper transcription service.
Handles model loading with caching and transcription.
Supports both faster-whisper (preferred) and openai-whisper backends.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from app import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Module-level model cache: model_name -> model_instance
_model_cache: dict = {}


def _import_backend():
    """Import the available whisper backend modules."""
    if config.WHISPER_BACKEND == "faster-whisper":
        from faster_whisper import WhisperModel

        return {"WhisperModel": WhisperModel}
    elif config.WHISPER_BACKEND == "openai-whisper":
        import whisper

        return {"whisper": whisper}
    return {}


_backend = _import_backend()


def get_cached_models() -> list[str]:
    """Return list of currently loaded model names."""
    return list(_model_cache.keys())


def _evict_other_models(keep_model: str) -> None:
    """Evict all models except the one about to be loaded (LRU-1)."""
    to_evict = [name for name in _model_cache if name != keep_model]
    for name in to_evict:
        logger.info(f"Evicting model '{name}' from cache to free memory")
        del _model_cache[name]


def _load_model_faster_whisper(model_name: str):
    """Load a model using faster-whisper."""
    WhisperModel = _backend["WhisperModel"]
    logger.info(f"Loading faster-whisper model: {model_name}")
    kwargs = {"device": "cpu", "compute_type": "int8"}
    if config.MODEL_CACHE_DIR:
        kwargs["download_root"] = config.MODEL_CACHE_DIR
    model = WhisperModel(model_name, **kwargs)
    logger.info(f"Model {model_name} loaded successfully")
    return model


def _load_model_openai(model_name: str):
    """Load a model using openai-whisper."""
    whisper = _backend["whisper"]
    logger.info(f"Loading openai-whisper model: {model_name}")
    kwargs = {}
    if config.MODEL_CACHE_DIR:
        kwargs["download_root"] = config.MODEL_CACHE_DIR
    model = whisper.load_model(model_name, **kwargs)
    logger.info(f"Model {model_name} loaded successfully")
    return model


def get_model(model_name: str):
    """
    Get a loaded model instance, loading it if not cached.
    Evicts previously cached models before loading a new one
    to keep memory bounded (LRU-1).
    """
    if model_name not in _model_cache:
        _evict_other_models(model_name)
        if config.WHISPER_BACKEND == "faster-whisper":
            _model_cache[model_name] = _load_model_faster_whisper(model_name)
        elif config.WHISPER_BACKEND == "openai-whisper":
            _model_cache[model_name] = _load_model_openai(model_name)
        else:
            raise RuntimeError("No whisper backend is installed.")
    return _model_cache[model_name]


def _transcribe_faster_whisper(
    model, file_path: Path, language: str | None, task: str
) -> dict[str, Any]:
    """Transcribe using faster-whisper."""
    kwargs: dict[str, Any] = {"beam_size": 5}
    if language and language != "auto":
        kwargs["language"] = language
    if task:
        kwargs["task"] = task

    segments_generator, info = model.transcribe(str(file_path), **kwargs)
    segments = list(segments_generator)

    normalized_segments = []
    full_text_parts = []
    for i, seg in enumerate(segments):
        normalized_segments.append(
            {
                "id": i,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
            }
        )
        full_text_parts.append(seg.text.strip())

    return {
        "text": " ".join(full_text_parts).strip(),
        "segments": normalized_segments,
        "language": info.language,
        "duration": round(info.duration, 3),
    }


def _extract_duration(segments: list[dict[str, Any]]) -> float:
    """Extract total duration from openai-whisper segments."""
    if not segments:
        return 0.0
    last_end: float = segments[-1].get("end", 0.0)
    return round(last_end, 3)


def _transcribe_openai(
    model, file_path: Path, language: str | None, task: str
) -> dict[str, Any]:
    """Transcribe using openai-whisper."""
    kwargs: dict[str, Any] = {"verbose": False}
    if language and language != "auto":
        kwargs["language"] = language
    if task:
        kwargs["task"] = task

    result = model.transcribe(str(file_path), **kwargs)

    normalized_segments = []
    for seg in result.get("segments", []):
        normalized_segments.append(
            {
                "id": seg.get("id", 0),
                "start": round(seg.get("start", 0.0), 3),
                "end": round(seg.get("end", 0.0), 3),
                "text": seg.get("text", "").strip(),
            }
        )

    return {
        "text": result.get("text", "").strip(),
        "segments": normalized_segments,
        "language": result.get("language", "unknown"),
        "duration": _extract_duration(result.get("segments", [])),
    }


def transcribe(
    file_path: Path, model_name: str, language: str, task: str
) -> dict[str, Any]:
    """Run transcription on an audio/video file."""
    if not config.WHISPER_BACKEND:
        raise RuntimeError(
            "No whisper backend installed. "
            "Please install faster-whisper or openai-whisper."
        )

    if not config.FFMPEG_AVAILABLE:
        raise RuntimeError(
            "ffmpeg is not available on this system. "
            "Please install ffmpeg to process audio/video files."
        )

    model = get_model(model_name)
    lang = None if language == "auto" else language

    try:
        if config.WHISPER_BACKEND == "faster-whisper":
            return _transcribe_faster_whisper(model, file_path, lang, task)
        else:
            return _transcribe_openai(model, file_path, lang, task)
    except Exception as exc:
        logger.error(f"Transcription failed: {exc}")
        if config.DEBUG:
            logger.error(traceback.format_exc())
        raise
