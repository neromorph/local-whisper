"""
File handling utilities.
Provides filename sanitization, validation, temp file management, and cleanup.
"""

import re
import tempfile
import unicodedata
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

_SAFE_FILENAME_RE = re.compile(r"[^\w\-. ]")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize an uploaded filename to prevent directory traversal
    and remove dangerous characters.
    """
    filename = unicodedata.normalize("NFKD", filename)
    filename = Path(filename).name
    filename = _SAFE_FILENAME_RE.sub("_", filename)
    filename = filename.lstrip(".")
    if len(filename) > 200:
        name, ext = Path(filename).stem, Path(filename).suffix
        filename = name[:200 - len(ext)] + ext
    return filename or "upload"


def validate_extension(filename: str) -> bool:
    """Check if the file extension is in the allowed set."""
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext in config.ALLOWED_EXTENSIONS


def validate_size(file_size: int) -> bool:
    """Check if the file size is within the configured limit."""
    return file_size <= config.MAX_UPLOAD_BYTES


def cleanup_temp(file_path: Path | None) -> None:
    """Safely delete a temporary file, ignoring errors."""
    if file_path and file_path.exists():
        try:
            file_path.unlink()
            logger.debug(f"Cleaned up temp file: {file_path}")
        except OSError as exc:
            logger.warning(f"Failed to cleanup temp file {file_path}: {exc}")


async def stream_upload_temp(upload_file: UploadFile, max_bytes: int) -> Path:
    """
    Stream an uploaded file directly to disk, rejecting mid-stream if
    the size exceeds the configured limit.  Uses tempfile for atomic,
    race-safe creation.

    Args:
        upload_file: FastAPI UploadFile instance.
        max_bytes: Maximum allowed file size in bytes.

    Returns:
        Path to the saved temporary file.

    Raises:
        HTTPException: 413 if the file exceeds the size limit.
    """
    safe_name = sanitize_filename(upload_file.filename or "upload")
    suffix = Path(safe_name).suffix or ".tmp"

    tmp = tempfile.NamedTemporaryFile(
        suffix=suffix,
        dir=config.TEMP_DIR,
        delete=False,
    )
    size = 0
    chunk_size = 64 * 1024  # 64 KB
    try:
        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                tmp.close()
                Path(tmp.name).unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"File too large ({size / 1024 / 1024:.1f} MB). "
                        f"Maximum allowed: {max_bytes // 1024 // 1024} MB"
                    ),
                )
            tmp.write(chunk)
    finally:
        tmp.close()

    logger.debug(f"Saved streamed upload ({size} bytes) to {tmp.name}")
    return Path(tmp.name)
