"""
Voice Server - FastAPI Application Entry Point

Runs on port 8090.

API Endpoints:
  TTS (Text to Speech):
    POST /tts                 - Convert text to speech
    GET  /tts/voices          - List Chinese voices
    GET  /tts/health          - TTS health check

  ASR (Speech to Text):
    POST /asr                 - Batch recognize from audio file
    WS   /asr/stream          - Real-time streaming ASR
    GET  /asr/health          - ASR health check

  KWS (Wake Word Detection):
    POST /kws/check           - Check audio for keywords
    GET  /kws/keywords        - List configured keywords
    WS   /kws/stream          - Real-time keyword spotting
    GET  /kws/health          - KWS health check

  System:
    GET  /health              - Overall health check
    GET  /                    - API info
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.logger import get_logger
from app.routers import tts, asr, kws

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("=" * 60)
    logger.info("Voice Server starting on port {}", settings.server.port)
    logger.info("Edge-TTS: {} (voice={})",
                "enabled" if settings.edge_tts.enabled else "disabled",
                settings.edge_tts.default_voice)
    logger.info("Sherpa-TTS: {}", "enabled" if settings.sherpa_tts.enabled else "disabled")
    logger.info("Sherpa-ASR: {}", "enabled" if settings.sherpa_asr.enabled else "disabled")
    logger.info("Sherpa-KWS: {}", "enabled" if settings.sherpa_kws.enabled else "disabled")
    logger.info("VAD: {}", "enabled" if settings.vad.enabled else "disabled")
    logger.info("=" * 60)

    # Log model availability
    from app.services.model_manager import model_manager

    if not settings.edge_tts.enabled:
        logger.warning("edge-tts disabled - no primary TTS engine")

    if not settings.sherpa_tts.enabled:
        logger.info("Sherpa-TTS not enabled - TTS fallback unavailable. "
                     "Set sherpa_tts.enabled=true in config.yaml after model download.")

    if not settings.sherpa_asr.enabled:
        logger.info("Sherpa-ASR not enabled - ASR unavailable. "
                     "Set sherpa_asr.enabled=true in config.yaml after model download.")

    if not settings.sherpa_kws.enabled:
        logger.info("Sherpa-KWS not enabled - wake word detection unavailable. "
                     "Set sherpa_kws.enabled=true in config.yaml after model download.")

    # Pre-load enabled models on startup
    logger.info("-" * 60)
    logger.info("Pre-loading models...")

    if settings.sherpa_kws.enabled:
        logger.info("Loading KWS model...")
        try:
            _ = model_manager.kws_model
            if model_manager._kws_model is not None:
                logger.info("KWS model loaded successfully")
            else:
                logger.warning("KWS model failed to load (check model files)")
        except Exception as e:
            logger.error("KWS model load error: {}", e)

    if settings.sherpa_asr.enabled:
        logger.info("Loading ASR model...")
        try:
            _ = model_manager.asr_model
            if model_manager._asr_model is not None:
                logger.info("ASR model loaded successfully")
            else:
                logger.warning("ASR model failed to load (check model files)")
        except Exception as e:
            logger.error("ASR model load error: {}", e)

    if settings.vad.enabled:
        logger.info("Loading VAD model...")
        try:
            _ = model_manager.vad_model
            if model_manager._vad_model is not None:
                logger.info("VAD model loaded successfully")
            else:
                logger.warning("VAD model failed to load (check model files)")
        except Exception as e:
            logger.error("VAD model load error: {}", e)

    if settings.sherpa_tts.enabled:
        logger.info("Loading Sherpa-TTS model (310MB, may take a moment)...")
        try:
            _ = model_manager.tts_model
            if model_manager._tts_model is not None:
                logger.info("Sherpa-TTS model loaded successfully (num_speakers={})",
                            model_manager._tts_model.num_speakers)
            else:
                logger.warning("Sherpa-TTS model failed to load (check model files)")
        except Exception as e:
            logger.error("Sherpa-TTS model load error: {}", e)

    logger.info("Voice Server ready. API docs at http://localhost:{}/docs",
                settings.server.port)
    logger.info("=" * 60)

    yield

    logger.info("Voice Server shutting down...")


app = FastAPI(
    title="Voice Server",
    description=(
        "Python voice service for BladeX AI Platform.\n\n"
        "**Capabilities:**\n"
        "- TTS: edge-tts (online, primary) + Sherpa-ONNX Kokoro (offline, fallback)\n"
        "- ASR: Sherpa-ONNX Streaming Zipformer Bilingual (offline)\n"
        "- KWS: Sherpa-ONNX Zipformer 3.3MB (offline, wake word detection)\n\n"
        "**Architecture:** Hybrid online/offline with smart routing"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
    allow_credentials=True,
)

# Register routers
app.include_router(tts.router)
app.include_router(asr.router)
app.include_router(kws.router)


@app.get("/", summary="API Info")
async def root():
    """Root endpoint with API information."""
    from app.services.model_manager import model_manager
    return {
        "name": "Voice Server",
        "version": "1.0.0",
        "description": "Python voice service for BladeX AI Platform",
        "endpoints": {
            "tts": {
                "synthesize_query": "POST /tts",
                "synthesize_body": "POST /tts/synthesize",
                "voices": "GET /tts/voices",
                "health": "GET /tts/health",
            },
            "asr": {
                "recognize": "POST /asr",
                "stream": "WS /asr/stream",
                "health": "GET /asr/health",
            },
            "kws": {
                "check": "POST /kws/check",
                "keywords": "GET /kws/keywords",
                "stream": "WS /kws/stream",
                "health": "GET /kws/health",
            },
            "system": {
                "health": "GET /health",
            },
        },
        "models": model_manager.status(),
        "timestamp": time.time(),
    }


@app.get("/health", summary="Health Check")
async def health():
    """Overall health check for all voice services."""
    from app.services.model_manager import model_manager
    status = model_manager.status()
    return {
        "status": "ok" if any(status.values()) else "degraded",
        "timestamp": time.time(),
        "engines": status,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
        log_level=settings.server.log_level,
        reload=False,
    )
