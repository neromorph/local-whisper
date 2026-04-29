"""
Application configuration loaded from environment variables.
Provides centralized, type-safe config access.
"""

import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = Path(os.getenv("TEMP_DIR", "tmp")).resolve()
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "")

# Server
DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

# CORS
ALLOW_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("ALLOW_ORIGINS", "http://localhost:8000").split(",")
    if origin.strip()
]

# Upload limits
MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "2000"))
MAX_UPLOAD_BYTES: int = MAX_UPLOAD_MB * 1024 * 1024

# Allowed file extensions (audio/video)
ALLOWED_EXTENSIONS: set[str] = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mkv",
    "mov",
    "webm",
    "flac",
    "ogg",
    "aac",
    "wma",
    "aiff",
}

# Concurrency & timeout
MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "1"))
MAX_TRANSCRIPTION_SECONDS: int = int(os.getenv("MAX_TRANSCRIPTION_SECONDS", "1800"))

# URL download limits
MAX_URL_DOWNLOAD_MB: int = int(os.getenv("MAX_URL_DOWNLOAD_MB", "500"))
MAX_URL_DOWNLOAD_BYTES: int = MAX_URL_DOWNLOAD_MB * 1024 * 1024
URL_TIMEOUT_SECONDS: int = int(os.getenv("URL_TIMEOUT_SECONDS", "300"))

# Allowed URL schemes for URL transcription mode
ALLOWED_URL_SCHEMES: set[str] = {"http", "https"}

# Whisper model options (large models excluded to protect disk storage)
WHISPER_MODELS: list[str] = [
    "tiny",
    "base",
    "small",
    "medium",
    "turbo",
]
DEFAULT_MODEL: str = "base"

# Default transcription settings
DEFAULT_LANGUAGE: str = "auto"
DEFAULT_TASK: str = "transcribe"

# Valid inputs
VALID_TASKS: set[str] = {"transcribe", "translate"}
VALID_LANGUAGES: set[str] = {
    "auto",
    "af",
    "am",
    "ar",
    "as",
    "az",
    "ba",
    "be",
    "bg",
    "bn",
    "bo",
    "br",
    "bs",
    "ca",
    "cs",
    "cy",
    "da",
    "de",
    "el",
    "en",
    "es",
    "et",
    "eu",
    "fa",
    "fi",
    "fo",
    "fr",
    "gl",
    "gu",
    "ha",
    "haw",
    "he",
    "hi",
    "hr",
    "ht",
    "hu",
    "hy",
    "id",
    "is",
    "it",
    "ja",
    "jw",
    "ka",
    "kk",
    "km",
    "kn",
    "ko",
    "la",
    "lb",
    "ln",
    "lo",
    "lt",
    "lv",
    "mg",
    "mi",
    "mk",
    "ml",
    "mn",
    "mr",
    "ms",
    "mt",
    "my",
    "ne",
    "nl",
    "nn",
    "no",
    "oc",
    "pa",
    "pl",
    "ps",
    "pt",
    "ro",
    "ru",
    "sa",
    "sd",
    "si",
    "sk",
    "sl",
    "sn",
    "so",
    "sq",
    "sr",
    "su",
    "sv",
    "sw",
    "ta",
    "te",
    "tg",
    "th",
    "tk",
    "tl",
    "tr",
    "tt",
    "uk",
    "ur",
    "uz",
    "vi",
    "yi",
    "yo",
    "yue",
    "zh",
}

# Ensure temp directory exists
TEMP_DIR.mkdir(parents=True, exist_ok=True)


# Detect available whisper backend at import time
def _detect_backend() -> str | None:
    """Try faster-whisper first, then openai-whisper."""
    try:
        import faster_whisper  # noqa: F401

        return "faster-whisper"
    except ImportError:
        pass
    try:
        import whisper  # noqa: F401

        return "openai-whisper"
    except ImportError:
        return None


WHISPER_BACKEND: str | None = _detect_backend()
FFMPEG_AVAILABLE: bool = shutil.which("ffmpeg") is not None


def _check_executable(name: str) -> bool:
    """Check if an executable is available, including venv bin directory."""
    if shutil.which(name) is not None:
        return True
    venv_bin = Path(sys.executable).parent
    return (venv_bin / name).exists()


YT_DLP_AVAILABLE: bool = _check_executable("yt-dlp")

# Check temp directory writability once at startup and cache the result
_temp_writable: bool = False
try:
    _probe = TEMP_DIR / ".probe_startup"
    _probe.write_text("ok")
    _probe.unlink()
    _temp_writable = True
except OSError:
    _temp_writable = False
TEMP_WRITABLE: bool = _temp_writable
