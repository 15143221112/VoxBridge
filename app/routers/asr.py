"""
ASR Router - Automatic Speech Recognition API endpoints.

POST /asr           - Batch ASR from audio file upload (WAV/MP3)
WS   /asr/stream    - Real-time streaming ASR via WebSocket
GET  /asr/health    - Check ASR engine status
"""

import numpy as np
from fastapi import APIRouter, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.services.asr_service import asr_service
from app.utils.logger import get_logger

logger = get_logger("asr_router")

router = APIRouter(prefix="/asr", tags=["ASR - Speech to Text"])


@router.post("", summary="Batch Speech Recognition")
async def recognize_speech(
    audio: UploadFile = File(..., description="Audio file (WAV or MP3)"),
):
    """
    Recognize speech from an uploaded audio file.

    **Supported formats:** WAV, MP3 (auto-converted to 16kHz mono PCM internally)

    **Model:** Sherpa-ONNX Streaming Zipformer Bilingual (zh-en)

    **Response:**
    ```json
    {
        "text": "recognized text",
        "confidence": 0.0,
        "duration_ms": 5000,
        "engine": "sherpa-onnx-streaming-zipformer-bilingual"
    }
    ```
    """
    return asr_service.recognize_file(audio)


@router.websocket("/stream")
async def asr_stream(websocket: WebSocket):
    """
    Real-time streaming ASR via WebSocket.

    **Protocol:**
    1. Client connects to `ws://localhost:8090/asr/stream`
    2. Client sends binary audio chunks (16-bit PCM, 16kHz, mono)
    3. Server responds with JSON:
       - `{"text": "...", "is_final": false}` - Partial result
       - `{"text": "...", "is_final": true, "reason": "endpoint"}` - Final (endpoint detected)
    4. Client sends `{"action": "stop"}` to end session

    **Audio format:** 16-bit signed PCM, 16kHz, mono (little-endian)
    """
    await websocket.accept()
    await asr_service.stream_recognize(websocket)


@router.get("/health", summary="ASR Health Check")
async def asr_health():
    """Check ASR engine availability."""
    from app.services.model_manager import model_manager
    status = model_manager.status()
    return {
        "sherpa_asr": status["sherpa_asr"],
        "vad": status["vad"],
        "model": "streaming-zipformer-bilingual-zh-en-2023-02-20" if status["sherpa_asr"] else None,
    }
