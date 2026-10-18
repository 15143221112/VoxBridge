"""
KWS Router - Keyword Spotting (Wake Word Detection) API endpoints.

POST /kws/check     - Check a chunk of audio for keywords
GET  /kws/keywords  - List configured keywords
WS   /kws/stream    - Real-time keyword spotting via WebSocket
GET  /kws/health    - Check KWS engine status
"""

import io
import numpy as np
from fastapi import APIRouter, UploadFile, File, WebSocket, Query
from fastapi.responses import JSONResponse

from app.services.kws_service import kws_service
from app.utils.logger import get_logger

logger = get_logger("kws_router")

router = APIRouter(prefix="/kws", tags=["KWS - Wake Word Detection"])


@router.post("/check", summary="Check Audio for Keywords")
async def check_keywords(
    audio: UploadFile = File(..., description="Audio file (WAV)"),
):
    """
    Check if an audio file contains any configured wake words.

    **Model:** Sherpa-ONNX Zipformer KWS (3.3MB, wenetspeech)

    **Response:**
    ```json
    {
        "detected": true,
        "keyword": "你好小智",
        "keyword_index": 0,
        "timestamp": 1234567890.0
    }
    ```
    """
    content = await audio.read()
    if not content:
        return JSONResponse(
            status_code=400,
            content={"error": "Empty audio file"}
        )

    # Load audio
    import librosa
    import tempfile
    import os

    suffix = "." + (audio.filename or "audio.wav").rsplit(".", 1)[-1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        samples, sr = librosa.load(tmp_path, sr=16000, mono=True)
        samples = (samples * 32767).astype(np.int16)
        result = kws_service.check_audio(samples)
        return result
    except Exception as e:
        logger.error("KWS check error: {}", e)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
    finally:
        os.unlink(tmp_path)


@router.get("/keywords", summary="List Configured Keywords")
async def list_keywords():
    """List all configured wake words and their thresholds."""
    keywords = kws_service.get_keywords()
    return {
        "count": len(keywords),
        "keywords": keywords,
    }


@router.websocket("/stream")
async def kws_stream(websocket: WebSocket):
    """
    Real-time wake word detection via WebSocket.

    **Protocol:**
    1. Client connects to `ws://localhost:8090/kws/stream`
    2. Client sends binary audio chunks (16-bit PCM, 16kHz, mono)
    3. Server responds with JSON:
       - `{"detected": true, "keyword": "你好小智", "timestamp": ...}` - Keyword detected
       - `{"detected": false, "timestamp": ...}` - No keyword (heartbeat)
    4. Client sends `{"action": "stop"}` to end session
    5. Client sends `{"action": "reset"}` to reset detection stream

    **Audio format:** 16-bit signed PCM, 16kHz, mono (little-endian)

    **Default keywords:** 你好小智, 小智同学, 唤醒小智, 开始录音, 停止录音
    """
    await websocket.accept()
    await kws_service.stream_detect(websocket)


@router.get("/health", summary="KWS Health Check")
async def kws_health():
    """Check KWS engine availability."""
    from app.services.model_manager import model_manager
    status = model_manager.status()
    keywords = kws_service.get_keywords()
    return {
        "sherpa_kws": status["sherpa_kws"],
        "model": "zipformer-kws-wenetspeech-3.3M-2024-01-01" if status["sherpa_kws"] else None,
        "keywords": keywords,
    }
