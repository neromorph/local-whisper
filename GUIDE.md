# Whisper Transcription App — Run Guide

This guide covers three ways to run the app:

1. [Native Python (no Docker)](#1-native-python)
2. [Docker](#2-docker)
3. [Docker Compose](#3-docker-compose)

---

## 1. Native Python

### Prerequisites

- Python 3.11+ (3.14 tested)
- `ffmpeg` installed system-wide
- A virtual environment (strongly recommended)

### Step 1: Create a virtual environment

```bash
cd /path/to/whisper/webapp
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate   # Windows
```

### Step 2: Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note:** `requirements.txt` prefers `faster-whisper`. If it fails to install, uncomment the `openai-whisper` fallback line and retry.

### Step 3: Configure environment (optional)

```bash
cp .env.example .env
# Edit .env with your preferences
```

### Step 4: Run the server

```bash
# Production-like
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Development (auto-reload + debug logs)
DEBUG=true uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 5: Open the app

Navigate to **http://localhost:8000** in your browser.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Verbose logging + traceback on errors |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `ALLOW_ORIGINS` | `http://localhost:8000` | CORS allowed origins (comma-separated) |
| `MAX_UPLOAD_MB` | `2000` | Max upload file size in MB |
| `TEMP_DIR` | `tmp` | Directory for temporary uploaded files |
| `MODEL_CACHE_DIR` | *(unset)* | Custom directory for caching Whisper models |
| `MAX_CONCURRENT_JOBS` | `1` | Max simultaneous transcription jobs |
| `MAX_TRANSCRIPTION_SECONDS` | `1800` | Hard timeout per transcription (seconds) |

Example:

```bash
DEBUG=true MAX_UPLOAD_MB=500 MODEL_CACHE_DIR=./models uvicorn app.main:app
```

### Running tests

```bash
pytest tests/test_routes.py -v
```

---

## 2. Docker

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed and running

### Build the image

```bash
cd /path/to/whisper/webapp
docker build -t whisper-app .
```

### Run the container

```bash
docker run -d \
  --name whisper-app \
  -p 8000:8000 \
  -e DEBUG=false \
  -e MAX_UPLOAD_MB=2000 \
  -e MODEL_CACHE_DIR=/models \
  -e TEMP_DIR=/app/tmp \
  -v "$(pwd)/models:/models" \
  -v "$(pwd)/tmp:/app/tmp" \
  --restart unless-stopped \
  whisper-app
```

### Verify it's running

```bash
# Health check
curl http://localhost:8000/health

# View logs
docker logs -f whisper-app
```

### Stop and remove

```bash
docker stop whisper-app
docker rm whisper-app
```

---

## 3. Docker Compose

### Prerequisites

- [Docker Compose](https://docs.docker.com/compose/install/) (v2+ recommended)

### Build and run (one command)

```bash
cd /path/to/whisper/webapp
docker compose up --build
```

Run in the background:

```bash
docker compose up --build -d
```

### Access the app

Open **http://localhost:8000** in your browser.

### View logs

```bash
docker compose logs -f
```

### Stop

```bash
docker compose down
```

### Persistent data

Docker Compose automatically creates and mounts two local directories:

| Host path | Container path | Purpose |
|-----------|---------------|---------|
| `./models` | `/models` | Cached Whisper models (survives rebuilds) |
| `./tmp` | `/app/tmp` | Temporary upload files |

These are created on first run if they don't exist.

### Environment variables (compose)

Edit `docker-compose.yml` or create a `.env` file in the same directory:

```bash
DEBUG=false
MAX_UPLOAD_MB=2000
MODEL_CACHE_DIR=/models
TEMP_DIR=/app/tmp
MAX_CONCURRENT_JOBS=1
MAX_TRANSCRIPTION_SECONDS=1800
ALLOW_ORIGINS=http://localhost:8000
```

### Optional: GPU profile (NVIDIA)

If you have an NVIDIA GPU and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) installed:

```bash
docker compose --profile gpu up --build
```

> **Note:** GPU mode requires modifying `app/services/whisper_service.py` to use `device="cuda"` and `compute_type="float16"`.

---

## Resource Considerations

### RAM usage by model size (CPU, INT8 quantization)

| Model | Approx RAM |
|-------|-----------|
| tiny | ~1 GB |
| base | ~1.5 GB |
| small | ~2 GB |
| medium | ~5 GB |
| large / large-v3 | ~10 GB |

Docker Desktop defaults to 2–4 GB RAM. Increase it in **Settings → Resources** if you plan to use medium or larger models.

### Model caching

- **First run** downloads the model from Hugging Face (~72 MB for tiny, ~3 GB for large-v3).
- **Subsequent runs** reuse the cached model in `./models` (host) or `/models` (container).
- The `models_cached` field in the `/health` response shows which models are currently loaded in memory.
- Only **one model is kept in memory at a time** (LRU-1 eviction). Loading a new model evicts the previous one.

### CPU vs GPU

- **CPU (default):** Works on any machine. Slower but universally compatible.
- **GPU:** ~2–4x faster. Requires NVIDIA GPU + Container Toolkit + CUDA-compatible base image.

### Concurrency

- `MAX_CONCURRENT_JOBS=1` (default) ensures only one transcription runs at a time.
- Increasing this shares CPU/RAM across simultaneous jobs — use with caution on laptops.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ffmpeg not available` | Install ffmpeg: `apt install ffmpeg` (Linux), `brew install ffmpeg` (macOS), or ensure it's in the Docker image |
| `No whisper backend installed` | Run `pip install faster-whisper` or `pip install openai-whisper` |
| `Connection reset by peer` during model download | Retry — Hugging Face may throttle; model will cache on success |
| Out of memory during transcription | Use a smaller model (tiny/base) or increase Docker RAM limit |
| Port 8000 already in use | Change the port: `PORT=8001 uvicorn app.main:app` or `docker run -p 8001:8000 ...` |
| Transcription timeout | Increase `MAX_TRANSCRIPTION_SECONDS` or use a smaller model |
| CORS errors in browser | Check `ALLOW_ORIGINS` matches your URL |

---

## Quick Reference

```bash
# Native
source .venv/bin/activate && uvicorn app.main:app

# Docker
docker build -t whisper-app . && docker run -p 8000:8000 whisper-app

# Docker Compose (recommended)
docker compose up --build

# Tests
pytest tests/test_routes.py -v
```
