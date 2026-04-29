# ---------------------------------------------------------------------------
# Whisper Transcription App — Dockerfile (multi-stage)
# ---------------------------------------------------------------------------
# Stage 1 (builder): compile native wheels with build-essential
# Stage 2 (final):   minimal image with only runtime deps
#
# NOTE: python:3.14-slim-trixie is used per project requirement.
# Trixie = Debian 13 (testing).  Pre-release Python means wheel
# availability for native extensions can be limited, so we keep
# build-essential in the builder stage.
#
# MEMORY CONSIDERATIONS (CPU-only, INT8 quantization):
#   tiny   ~ 1 GB   | base   ~ 1.5 GB
#   small  ~ 2 GB   | medium ~ 5 GB
#   large / large-v3 ~ 10 GB
# For GPU usage, cut the estimates roughly in half.
# ---------------------------------------------------------------------------

# ── Stage 1: Builder ───────────────────────────────────────────────────────
FROM python:3.14-slim-trixie AS builder

WORKDIR /build

# Install build toolchain + ffmpeg (needed for any audio decoding at build time)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a dedicated prefix
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Final ─────────────────────────────────────────────────────────
FROM python:3.14-slim-trixie AS final

# OCI labels (Dockerfile best practice)
LABEL org.opencontainers.image.title="local-whisper"
LABEL org.opencontainers.image.description="Local-first audio and video transcription powered by faster-whisper"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.url="https://github.com/neromorph/local-whisper"
LABEL org.opencontainers.image.source="https://github.com/neromorph/local-whisper"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.maintainer="neromorph"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime system deps only (no build toolchain)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Application code
COPY app/ ./app/
COPY static/ ./static/

# Pre-create app-managed directories with correct ownership
RUN groupadd -r appgroup && \
    useradd -r -g appgroup -d /app appuser && \
    mkdir -p /models /app/tmp && \
    chown -R appuser:appgroup /app /models

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
