# local-whisper

<!-- markdownlint-disable MD033 MD041 -->

![CI](https://img.shields.io/github/actions/workflow/status/neromorph/local-whisper/ci.yml?branch=main&logo=github&label=CI)
![Security](https://img.shields.io/github/actions/workflow/status/neromorph/local-whisper/security.yml?branch=main&logo=github&label=Security)
![Python](https://img.shields.io/badge/python-3.11%7C3.12%7C3.13-blue?logo=python&logoColor=yellow)
![License](https://img.shields.io/badge/license-MIT-green?logo=open-source-initiative&logoColor=white)
![Docker](https://img.shields.io/badge/ghcr.io-neromorph%2Flocal--whisper-blue?logo=docker)

<!-- markdownlint-enable MD033 MD041 -->

A **local-first**, self-hosted audio and video transcription web app powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper). No cloud, no subscriptions, no data leaving your machine.

Transcribe local files directly in your browser, or pull audio from a public URL (YouTube, podcasts, etc.) using `yt-dlp`. Choose from a range of Whisper model sizes, auto-detect language, and export results as plain text or SRT subtitles.

---

## Table of Contents

- [Why local-whisper?](#why-local-whisper)
- [Features](#features)
- [Screenshots](#screenshots)
- [Quick Start with Docker](#quick-start-with-docker)
- [Local Development](#local-development)
- [URL Mode](#url-mode)
- [Supported Formats](#supported-formats)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Why local-whisper?

Most transcription services send your audio to third-party servers — raising privacy concerns, imposing usage limits, and requiring subscriptions. `local-whisper` brings OpenAI's Whisper model directly to your own hardware, so your data never leaves your machine.

Whether you're a journalist transcribing interviews, a researcher processing audio datasets, or a developer integrating speech-to-text into your workflow, `local-whisper` gives you enterprise-quality transcription without the enterprise cloud.

---

## Features

- **Local-first** — All processing happens on your machine. No cloud, no data exfiltration.
- **Two transcription modes** — Upload audio/video files directly, or provide a public URL (YouTube, podcasts, and 1000+ other sites via `yt-dlp`).
- **Multiple Whisper models** — Choose from `tiny`, `base`, `small`, `medium`, and `turbo` to balance speed and accuracy.
- **Auto language detection** — Let Whisper detect the spoken language automatically, or specify it manually.
- **Translate to English** — Use Whisper's translation task to convert non-English speech to English text.
- **SRT subtitle export** — Generate timestamped subtitle files alongside plain text.
- **Model caching** — Downloaded models are cached locally and reused across sessions.
- **Background URL jobs** — URL transcription runs in the background with real-time status polling.
- **Job cancellation** — Cancel long-running transcription jobs at any time.
- **Docker + GPU support** — Optional NVIDIA GPU acceleration for significantly faster transcription.
- **Clean, minimal UI** — Plain HTML/CSS/JS frontend. No framework bloat.

---

## Screenshots

> **Screenshots coming soon.** The app features a minimal, dark-theme UI with:
>
> - A two-tab interface: **Upload File** and **URL Mode**
> - A drag-and-drop upload zone with file info display
> - Model, language, and task selectors
> - Real-time progress bar during transcription
> - A transcript viewer with Copy, Download .txt, and Download .SRT buttons

---

## Quick Start with Docker

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (with Docker Compose recommended)
- ~2–10 GB free disk space depending on chosen model

### One-command startup

```bash
# Pull and run with Docker Compose
docker compose up --build

# Or run the container directly
docker run -d \
  --name local-whisper \
  -p 8000:8000 \
  -e MAX_UPLOAD_MB=2000 \
  -e MODEL_CACHE_DIR=/models \
  -v "$(pwd)/models:/models" \
  -v "$(pwd)/tmp:/app/tmp" \
  --restart unless-stopped \
  ghcr.io/neromorph/local-whisper:latest
```

Then open **http://localhost:8000** in your browser.

### Pull latest image manually

```bash
docker pull ghcr.io/neromorph/local-whisper:latest
```

### GPU acceleration (NVIDIA)

```bash
docker compose --profile gpu up --build
```

Requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

---

## Local Development

### Prerequisites

- Python 3.11+
- `ffmpeg` installed system-wide
- A virtual environment (strongly recommended)

### 1. Clone and set up environment

```bash
git clone https://github.com/neromorph/local-whisper.git
cd local-whisper
python3 -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate     # Windows
```

### 2. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt

# For development (linters, tests)
pip install -r requirements-dev.txt
```

> **Note:** `requirements.txt` prefers `faster-whisper`. If installation fails, fall back to `openai-whisper` by uncommenting the appropriate line.

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env if needed (defaults work for local dev)
```

### 4. Run the server

```bash
# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Development (auto-reload + debug logs)
DEBUG=true uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** in your browser.

### 5. Run tests

```bash
# All tests
pytest -v

# With coverage
pytest --cov=app --cov-report=html -v
```

### 6. Run pre-commit hooks

```bash
pre-commit install --install-hooks
pre-commit run --all-files
```

---

## URL Mode

URL mode lets you transcribe audio from public internet sources without downloading anything locally first. It uses `yt-dlp` to extract the media and Whisper to transcribe it.

**Supported sources** include (but are not limited to):

- YouTube videos and Shorts
- Podcasts (Spotify, Apple Podcasts RSS feeds)
- Twitch streams and VODs
- Vimeo
- Rumble
- Local news sites with embedded audio
- Any site `yt-dlp` can extract audio from

**How it works:**

1. Paste a public URL into the URL input field
2. Click "Start Transcription"
3. The app fetches metadata (title, duration, uploader) in the background
4. A background job downloads and transcodes the audio
5. Poll the job status endpoint for real-time progress
6. When complete, view and export the transcript

**Security:** URL mode blocks private IP ranges (RFC 1918), localhost, and link-local addresses to prevent SSRF attacks. Only HTTP and HTTPS schemes are allowed.

---

## Supported Formats

| Format | Extension | MIME Type |
|--------|-----------|-----------|
| MP3 | `.mp3` | audio/mpeg |
| WAV | `.wav` | audio/wav |
| M4A | `.m4a` | audio/mp4 |
| MP4 | `.mp4` | video/mp4 |
| MKV | `.mkv` | video/x-matroska |
| MOV | `.mov` | video/quicktime |
| WebM | `.webm` | video/webm |
| FLAC | `.flac` | audio/flac |
| OGG | `.ogg` | audio/ogg |
| AAC | `.aac` | audio/aac |
| WMA | `.wma` | audio/x-wma |
| AIFF | `.aiff` | audio/aiff |

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable verbose logging and tracebacks |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `ALLOW_ORIGINS` | `http://localhost:8000` | CORS allowed origins (comma-separated) |
| `MAX_UPLOAD_MB` | `2000` | Max file upload size (MB) |
| `MAX_URL_DOWNLOAD_MB` | `500` | Max URL download size (MB) |
| `URL_TIMEOUT_SECONDS` | `300` | Timeout for URL downloads |
| `TEMP_DIR` | `tmp` | Temporary file directory |
| `MODEL_CACHE_DIR` | _(empty)_ | Custom Whisper model cache directory |
| `MAX_CONCURRENT_JOBS` | `1` | Max simultaneous transcription jobs |
| `MAX_TRANSCRIPTION_SECONDS` | `1800` | Hard timeout per transcription (seconds) |
| `HF_HUB_OFFLINE` | `1` | Disable HuggingFace Hub network (models from cache only) |

### Whisper Models

| Model | Parameters | Speed | VRAM | Accuracy |
|-------|-----------|-------|------|----------|
| `tiny` | 39 M | Fastest | ~1 GB | Lowest |
| `base` | 74 M | Fast | ~1 GB | Low |
| `small` | 244 M | Moderate | ~2 GB | Medium |
| `medium` | 769 M | Slow | ~5 GB | High |
| `turbo` | 809 M | Fast | ~6 GB | High |

---

## Architecture

```
webapp/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app entry point, CORS, lifespan
│   ├── config.py        # Environment variable configuration
│   ├── routes.py        # API endpoints (transcribe, health, jobs)
│   ├── services/
│   │   ├── whisper_service.py  # faster-whisper transcription
│   │   ├── job_service.py      # Background job state management
│   │   └── url_service.py      # URL validation + yt-dlp integration
│   └── utils/
│       ├── files.py     # Upload streaming, extension validation
│       └── logger.py    # Structured logging
├── static/
│   ├── index.html       # Single-page frontend
│   ├── style.css        # Custom styles
│   └── app.js           # Frontend JavaScript
├── tests/
│   ├── conftest.py      # Shared pytest fixtures
│   └── test_routes.py   # API integration tests
├── Dockerfile           # Multi-stage production image
├── docker-compose.yml   # Local dev with GPU profile
├── requirements.txt     # Production Python dependencies
└── requirements-dev.txt # Development + test dependencies
```

---

## Roadmap

- [ ] **v0.2.0** — Batch transcription (multiple files at once)
- [ ] **v0.3.0** — Timestamped segments with word-level highlighting
- [ ] **v0.4.0** — Diarization (speaker identification) integration
- [ ] **v0.5.0** — API key authentication for remote access
- [ ] **v1.0.0** — Stable release with plugin system

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, coding standards, and the PR process.

**Quick dev setup:**

```bash
git clone https://github.com/neromorph/local-whisper.git
cd local-whisper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install --install-hooks
pytest -v
```

---

## License

Licensed under the MIT License. See [LICENSE](LICENSE) for full text.

---

## Star History

If this project is useful to you, please consider giving it a star. It helps the project gain visibility and encourages ongoing development.
