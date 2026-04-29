"""
URL handling service for video/audio transcription.
Provides URL validation, metadata extraction, and audio downloading via yt-dlp.
"""

import ipaddress
import json
import re
import socket
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from app import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

# Private/internal IP ranges that should be rejected to mitigate SSRF
_PRIVATE_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),   # loopback
    ipaddress.ip_network("10.0.0.0/8"),     # private
    ipaddress.ip_network("172.16.0.0/12"),  # private
    ipaddress.ip_network("192.168.0.0/16"), # private
    ipaddress.ip_network("169.254.0.0/16"), # link-local
    ipaddress.ip_network("0.0.0.0/8"),      # current network
    ipaddress.ip_network("::1/128"),        # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),       # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),      # IPv6 link-local
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6
]

# Hostnames that imply localhost / internal access
_LOCAL_HOST_RE = re.compile(
    r"^(localhost|127\.\d+\.\d+\.\d+|0\.0\.0\.0|::1)$", re.IGNORECASE
)


def _is_private_host(hostname: str) -> bool:
    """Check if a hostname resolves to a private/internal address."""
    if not hostname:
        return True
    if _LOCAL_HOST_RE.match(hostname):
        return True
    try:
        # If hostname is an IP literal, check directly
        addr = ipaddress.ip_address(hostname)
        # Also check IPv4-mapped form (e.g. ::ffff:192.168.1.1)
        addrs_to_check = [addr]
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            addrs_to_check.append(addr.ipv4_mapped)
        for a in addrs_to_check:
            for network in _PRIVATE_IP_NETWORKS:
                if a in network:
                    return True
    except ValueError:
        # Not an IP — do a DNS lookup to get all addresses
        try:
            infos = socket.getaddrinfo(hostname, None)
            for _, _, _, _, sockaddr in infos:
                ip = sockaddr[0]
                try:
                    addr = ipaddress.ip_address(ip)
                    addrs_to_check = [addr]
                    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
                        addrs_to_check.append(addr.ipv4_mapped)
                    for a in addrs_to_check:
                        for network in _PRIVATE_IP_NETWORKS:
                            if a in network:
                                return True
                except ValueError:
                    continue
        except (socket.gaierror, OSError):
            # DNS resolution failed — treat as potentially internal
            logger.warning(f"Could not resolve hostname '{hostname}' for SSRF check")
            return True
    return False


def validate_url(url: str) -> None:
    """
    Validate a URL for security before downloading.

    Raises ValueError with a human-friendly message if the URL is invalid,
    uses a non-http(s) scheme, or points to a private/internal address.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL is required.")

    url = url.strip()
    if not url:
        raise ValueError("URL is required.")
    if len(url) > 2048:
        raise ValueError("URL is too long. Maximum length is 2048 characters.")

    parsed = urlparse(url)

    if parsed.scheme not in config.ALLOWED_URL_SCHEMES:
        raise ValueError(
            f"Invalid URL scheme '{parsed.scheme}'. Only HTTP and HTTPS links are supported."
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: missing hostname.")

    if _is_private_host(hostname):
        raise ValueError(
            "This URL points to a private or internal address and cannot be accessed."
        )

    # Basic sanity: must have a netloc and a path/query
    if not parsed.netloc:
        raise ValueError("Invalid URL format.")

    logger.debug(f"URL validated: {parsed.scheme}://{parsed.netloc}{parsed.path}")


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

class MediaMetadata:
    """Simple data holder for media metadata."""

    def __init__(self, title: str = "", duration: float = 0.0, uploader: str = ""):
        self.title = title
        self.duration = duration
        self.uploader = uploader

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "duration": round(self.duration, 2) if self.duration else 0,
            "uploader": self.uploader,
        }


def fetch_metadata(url: str) -> MediaMetadata:
    """
    Fetch metadata from a URL using yt-dlp without downloading.

    Returns MediaMetadata with title, duration, and uploader if available.
    Raises RuntimeError with human-friendly message on failure.
    """
    if not config.YT_DLP_AVAILABLE:
        raise RuntimeError("yt-dlp is not installed. Please install it to use URL transcription.")

    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--no-playlist",
        "--dump-json",
        "--no-download",
        "--socket-timeout", "30",
        url,
    ]

    logger.info(f"Fetching metadata for {urlparse(url).netloc}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Fetching media information timed out. The site may be slow or unreachable.") from None
    except FileNotFoundError:
        raise RuntimeError("yt-dlp executable not found. Please install yt-dlp.") from None
    except Exception as exc:
        raise RuntimeError(f"Could not fetch media information: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # Try to produce a friendly error from yt-dlp stderr
        if "Private video" in stderr or "private" in stderr.lower():
            raise RuntimeError("This video is private and cannot be accessed.")
        if "Unsupported URL" in stderr or "unsupported" in stderr.lower():
            raise RuntimeError("This URL is not supported. Try a YouTube or direct media link.")
        if "Sign in" in stderr or "login" in stderr.lower():
            raise RuntimeError("This content requires a login and cannot be accessed.")
        logger.warning(f"yt-dlp metadata error: {stderr}")
        raise RuntimeError(f"Could not fetch media information. {stderr[:200]}")

    # yt-dlp --dump-json may output multiple lines (playlists). Take the first.
    first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    if not first_line:
        raise RuntimeError("No metadata returned for this URL.")

    try:
        info = json.loads(first_line)
    except json.JSONDecodeError:
        raise RuntimeError("Could not parse media metadata.") from None

    metadata = MediaMetadata(
        title=info.get("title") or "",
        duration=info.get("duration") or 0.0,
        uploader=info.get("uploader") or "",
    )
    logger.info(
        f"Metadata fetched: title='{metadata.title}', duration={metadata.duration}s, uploader='{metadata.uploader}'"
    )
    return metadata


# ---------------------------------------------------------------------------
# Audio download
# ---------------------------------------------------------------------------

def download_audio(
    url: str,
    output_dir: Path,
    cancel_event=None,
    progress_callback=None,
) -> Path:
    """
    Download audio from a URL using yt-dlp and extract it to an audio file.

    Args:
        url: The media URL to download.
        output_dir: Directory to save the downloaded file.
        cancel_event: Optional threading.Event to check for cancellation.
        progress_callback: Optional callable(progress_pct: int, message: str)
                           called periodically during download.

    Returns:
        Path to the extracted audio file.

    Raises:
        RuntimeError: If yt-dlp fails or audio cannot be extracted.
        ValueError: If output_dir is invalid.
    """
    if not config.YT_DLP_AVAILABLE:
        raise RuntimeError("yt-dlp is not installed. Please install it to use URL transcription.")

    if not output_dir.exists() or not output_dir.is_dir():
        raise ValueError(f"Output directory does not exist: {output_dir}")

    # Use a UUID-based template stem. yt-dlp replaces %(ext)s with the actual extension.
    # No NamedTemporaryFile is created here, so there is no empty temp file leak.
    stem = f"url_audio_{uuid.uuid4().hex}"
    output_template = str(output_dir / f"{stem}.%(ext)s")
    expected_path = output_dir / f"{stem}.mp3"

    # yt-dlp options:
    #   -x           : extract audio
    #   --audio-format mp3 : convert to mp3
    #   --audio-quality 0  : best quality
    #   --max-filesize     : reject oversized downloads
    #   --socket-timeout   : network timeout
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--no-playlist",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--max-filesize", str(config.MAX_URL_DOWNLOAD_BYTES),
        "--socket-timeout", "30",
        "-o", output_template,
        url,
    ]

    logger.info(f"Starting audio download for {urlparse(url).netloc}")
    logger.debug(f"yt-dlp output template: {output_template}")

    try:
        # stdout=DEVNULL avoids a pipe buffer deadlock if yt-dlp writes >64KB to stdout
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        raise RuntimeError("yt-dlp executable not found. Please install yt-dlp.") from None

    # Simple stderr polling loop to catch cancel + log progress
    try:
        # Wait with timeout and poll for cancellation
        returncode = None
        elapsed = 0
        poll_interval = 0.5  # seconds
        while returncode is None:
            if cancel_event and cancel_event.is_set():
                logger.info("Download cancelled by user")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise RuntimeError("Download cancelled.")

            returncode = process.poll()
            if returncode is None:
                time.sleep(poll_interval)
                elapsed += poll_interval
                if elapsed > config.URL_TIMEOUT_SECONDS:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise RuntimeError("Download timed out. The file may be too large or the connection too slow.")

                if progress_callback and elapsed % 2 < poll_interval:
                    progress_callback(-1, "Downloading audio...")

        stdout, stderr = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        raise RuntimeError("Download process did not respond and was killed.") from None
    except RuntimeError:
        raise
    except Exception as exc:
        process.kill()
        raise RuntimeError(f"Download failed: {exc}") from exc

    if returncode != 0:
        stderr_clean = (stderr or "").strip()
        if "File is larger than max-filesize" in stderr_clean:
            raise RuntimeError(
                f"The audio/video file is too large. Maximum allowed: {config.MAX_URL_DOWNLOAD_MB} MB."
            )
        if "Private video" in stderr_clean:
            raise RuntimeError("This video is private and cannot be accessed.")
        if "Unsupported URL" in stderr_clean or "unsupported" in stderr_clean.lower():
            raise RuntimeError("This URL is not supported. Try a YouTube or direct media link.")
        if "Sign in" in stderr_clean or "login" in stderr_clean.lower():
            raise RuntimeError("This content requires a login and cannot be accessed.")
        logger.error(f"yt-dlp download error: {stderr_clean}")
        raise RuntimeError(f"Download failed: {stderr_clean[:300]}")

    if not expected_path.exists():
        # Fallback: look for any file starting with the same stem in output_dir
        candidates = list(output_dir.glob(f"{stem}*"))
        audio_candidates = [c for c in candidates if c.suffix.lower() in (".mp3", ".m4a", ".webm", ".ogg", ".opus", ".wav", ".flac")]
        if audio_candidates:
            expected_path = audio_candidates[0]
        elif candidates:
            expected_path = candidates[0]
        else:
            raise RuntimeError("Download completed but no audio file was found.")

    file_size = expected_path.stat().st_size
    logger.info(f"Audio downloaded: {expected_path} ({file_size} bytes)")

    if file_size == 0:
        expected_path.unlink(missing_ok=True)
        raise RuntimeError("Downloaded audio file is empty.")

    if progress_callback:
        progress_callback(100, "Download complete")

    return expected_path
