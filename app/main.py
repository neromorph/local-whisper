"""
FastAPI application entry point.
Configures CORS, static files, routes, and exception handling.
"""

import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.routes import router
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Whisper Transcription App")
    logger.info(f"Whisper backend: {config.WHISPER_BACKEND or 'NONE (install required)'}")
    logger.info(f"ffmpeg available: {config.FFMPEG_AVAILABLE}")
    logger.info(f"Debug mode: {config.DEBUG}")
    logger.info(f"Temp directory: {config.TEMP_DIR}")
    logger.info(f"Temp writable: {config.TEMP_WRITABLE}")
    logger.info(f"Max concurrent jobs: {config.MAX_CONCURRENT_JOBS}")
    logger.info(f"Max transcription timeout: {config.MAX_TRANSCRIPTION_SECONDS}s")
    yield
    logger.info("Shutting down Whisper Transcription App")


app = FastAPI(
    title="Whisper Transcription App",
    description="Local-first audio/video transcription with OpenAI Whisper",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = config.BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(router)


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Catch-all exception handler for unexpected errors."""
    logger.error(f"Unhandled exception: {exc}")
    if config.DEBUG:
        logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "detail": str(exc) if not config.DEBUG else traceback.format_exc(),
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="debug" if config.DEBUG else "info",
    )
