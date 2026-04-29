"""
Functional tests for the Whisper transcription service.
Uses the JFK audio sample to verify real transcription works end-to-end.

Marked as 'slow' — skipped in CI by default. Run locally with:
    pytest tests/test_functional.py -v
"""

from pathlib import Path

import pytest

from app.services.whisper_service import get_model, transcribe

JFK_FLAC = Path(__file__).parent / "jfk.flac"


@pytest.fixture(scope="module")
def tiny_model():
    """Load the tiny model once for all tests in this module."""
    return get_model("tiny")


@pytest.mark.slow
def test_transcribe_english_with_tiny():
    """Transcribe JFK audio with tiny model and verify expected content."""
    assert JFK_FLAC.exists(), f"jfk.flac not found at {JFK_FLAC}"

    result = transcribe(JFK_FLAC, "tiny", "en", "transcribe")

    assert "text" in result
    assert result["language"] == "en"
    assert len(result["text"]) > 0

    text_lower = result["text"].lower()
    assert "my fellow americans" in text_lower
    assert "your country" in text_lower


@pytest.mark.slow
def test_translate_to_english_with_tiny():
    """Transcribe JFK audio with translate task (English → English, still works)."""
    result = transcribe(JFK_FLAC, "tiny", "en", "translate")

    assert "text" in result
    assert len(result["text"]) > 0
    assert "segments" in result
    assert len(result["segments"]) > 0


@pytest.mark.slow
def test_transcribe_auto_detect_language():
    """Transcribe with auto language detection."""
    result = transcribe(JFK_FLAC, "tiny", "auto", "transcribe")

    assert "text" in result
    assert result["language"] == "en"
    assert len(result["text"]) > 0


@pytest.mark.slow
def test_transcribe_returns_segments_with_timestamps():
    """Verify segments have proper start/end timestamps."""
    result = transcribe(JFK_FLAC, "tiny", "en", "transcribe")

    segments = result["segments"]
    assert len(segments) > 0

    for seg in segments:
        assert "start" in seg
        assert "end" in seg
        assert "text" in seg
        assert seg["start"] < seg["end"]
        assert len(seg["text"].strip()) > 0


@pytest.mark.slow
def test_transcribe_returns_duration():
    """Verify total duration is reported."""
    result = transcribe(JFK_FLAC, "tiny", "en", "transcribe")

    assert "duration" in result
    assert result["duration"] > 0
    # JFK speech is roughly 10-12 seconds
    assert 5 < result["duration"] < 20
