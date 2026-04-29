"""
Integration tests for FastAPI routes.
Uses fastapi.testclient.TestClient — no HTTP server required.
"""

from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


def test_health_returns_expected_fields():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "whisper_backend" in data
    assert "ffmpeg_available" in data
    assert "models_cached" in data
    assert "temp_dir_writable" in data


def test_extensions_returns_allowed_set():
    response = client.get("/extensions")
    assert response.status_code == 200
    data = response.json()
    assert "extensions" in data
    assert "mp3" in data["extensions"]
    assert "wav" in data["extensions"]


def test_transcribe_missing_file():
    response = client.post(
        "/transcribe", data={"model": "tiny", "language": "en", "task": "transcribe"}
    )
    assert response.status_code == 422


def test_transcribe_invalid_extension():
    response = client.post(
        "/transcribe",
        data={"model": "tiny", "language": "en", "task": "transcribe"},
        files={"file": ("virus.exe", b"bad content", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_transcribe_invalid_model():
    response = client.post(
        "/transcribe",
        data={"model": "huge", "language": "en", "task": "transcribe"},
        files={"file": ("test.mp3", b"audio", "audio/mpeg")},
    )
    assert response.status_code == 400
    assert "Invalid model" in response.json()["detail"]


def test_transcribe_invalid_task():
    response = client.post(
        "/transcribe",
        data={"model": "tiny", "language": "en", "task": "summarize"},
        files={"file": ("test.mp3", b"audio", "audio/mpeg")},
    )
    assert response.status_code == 400
    assert "Invalid task" in response.json()["detail"]


def test_transcribe_invalid_language():
    response = client.post(
        "/transcribe",
        data={"model": "tiny", "language": "klingon", "task": "transcribe"},
        files={"file": ("test.mp3", b"audio", "audio/mpeg")},
    )
    assert response.status_code == 400
    assert "Invalid language" in response.json()["detail"]


def test_transcribe_oversized_file():
    # Create a payload slightly larger than the limit
    original_limit = config.MAX_UPLOAD_BYTES
    config.MAX_UPLOAD_BYTES = 10
    try:
        response = client.post(
            "/transcribe",
            data={"model": "tiny", "language": "en", "task": "transcribe"},
            files={"file": ("test.mp3", b"x" * 20, "audio/mpeg")},
        )
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()
    finally:
        config.MAX_UPLOAD_BYTES = original_limit


def test_serve_frontend():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# URL transcription tests
# ---------------------------------------------------------------------------


def test_transcribe_url_success_or_missing_ytdlp():
    # If yt-dlp is installed, we get a job_id immediately (200).
    # If yt-dlp is missing, we get 503.
    # The background pipeline may later fail on metadata, but the endpoint itself is tested here.
    response = client.post(
        "/transcribe/url",
        json={
            "url": "https://example.com/video",
            "model": "base",
            "language": "auto",
            "task": "transcribe",
        },
    )
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is True
        assert "job_id" in data


def test_transcribe_url_invalid_model():
    response = client.post(
        "/transcribe/url",
        json={
            "url": "https://example.com/video",
            "model": "huge",
            "language": "auto",
            "task": "transcribe",
        },
    )
    assert response.status_code == 400
    assert "Invalid model" in response.json()["detail"]


def test_transcribe_url_invalid_task():
    response = client.post(
        "/transcribe/url",
        json={
            "url": "https://example.com/video",
            "model": "base",
            "language": "auto",
            "task": "summarize",
        },
    )
    assert response.status_code == 400
    assert "Invalid task" in response.json()["detail"]


def test_transcribe_url_invalid_language():
    response = client.post(
        "/transcribe/url",
        json={
            "url": "https://example.com/video",
            "model": "base",
            "language": "klingon",
            "task": "transcribe",
        },
    )
    assert response.status_code == 400
    assert "Invalid language" in response.json()["detail"]


def test_transcribe_url_invalid_url_scheme():
    response = client.post(
        "/transcribe/url",
        json={
            "url": "ftp://example.com/video",
            "model": "base",
            "language": "auto",
            "task": "transcribe",
        },
    )
    assert response.status_code == 400
    assert "scheme" in response.json()["detail"].lower()


def test_transcribe_url_private_ip():
    response = client.post(
        "/transcribe/url",
        json={
            "url": "http://192.168.1.1/video",
            "model": "base",
            "language": "auto",
            "task": "transcribe",
        },
    )
    assert response.status_code == 400
    assert "private" in response.json()["detail"].lower()


def test_transcribe_url_localhost():
    response = client.post(
        "/transcribe/url",
        json={
            "url": "http://localhost:8000/video",
            "model": "base",
            "language": "auto",
            "task": "transcribe",
        },
    )
    assert response.status_code == 400
    assert "private" in response.json()["detail"].lower()


def test_job_status_not_found():
    response = client.get("/jobs/nonexistent-job/status")
    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]


def test_job_cancel_not_found():
    response = client.post("/jobs/nonexistent-job/cancel")
    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]
