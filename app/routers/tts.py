"""
TTS Router - Text to Speech API endpoints.

POST /tts             - Convert text to speech (Query String 参数，短文本)
POST /tts/synthesize  - Convert text to speech (JSON Body 参数，长文本推荐)
GET  /tts/voices      - List available Chinese voices
GET  /tts/health      - Check TTS engine status
"""

from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.tts_service import tts_service
from app.utils.logger import get_logger

logger = get_logger("tts_router")

router = APIRouter(prefix="/tts", tags=["TTS - Text to Speech"])


# ============================================================
# JSON Body 请求模型（长文本推荐，不受 URL 长度限制）
# ============================================================
class TtsRequest(BaseModel):
    """TTS 合成请求体（JSON Body）"""
    text: str = Field(..., description="要合成的文本，最大 5000 字", max_length=5000)
    voice: Optional[str] = Field(None, description="发音人，如 zh-CN-XiaoxiaoNeural")
    rate: Optional[str] = Field(None, description="语速，如 +10% / -5%")
    pitch: Optional[str] = Field(None, description="音调，如 +2Hz / -1Hz")
    volume: Optional[str] = Field(None, description="音量，如 +20% / -10%")
    fallback: bool = Field(False, description="true=跳过 edge-tts 直接用离线引擎")


@router.post("", summary="Text to Speech")
async def text_to_speech(
    text: str = Query(..., description="Text to synthesize", max_length=5000),
    voice: Optional[str] = Query(None, description="Voice name (e.g., zh-CN-XiaoxiaoNeural)"),
    rate: Optional[str] = Query(None, description="Speech rate (e.g., +10%, -5%)"),
    pitch: Optional[str] = Query(None, description="Pitch (e.g., +2Hz)"),
    volume: Optional[str] = Query(None, description="Volume (e.g., +20%)"),
    fallback: bool = Query(False, description="If true, use offline Sherpa-ONNX directly"),
):
    """
    Convert text to speech audio.

    **Routing:**
    - Primary: edge-tts (Microsoft Azure Neural TTS, free, online)
    - Fallback: Sherpa-ONNX Kokoro (offline, local)

    **Response:**
    - Content-Type: audio/mpeg (edge-tts) or audio/wav (sherpa-onnx)
    - X-TTS-Engine header indicates which engine was used

    **Voice options (Chinese):**
    | Voice | Gender | Style |
    |-------|--------|-------|
    | zh-CN-XiaoxiaoNeural | Female | Natural, friendly |
    | zh-CN-YunxiNeural | Male | Calm, steady |
    | zh-CN-XiaoyiNeural | Female | Lively |
    | zh-CN-YunjianNeural | Male | Sporty |
    | zh-CN-YunyangNeural | Male | Professional broadcast |
    """
    return await tts_service.synthesize(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
        use_fallback=fallback,
    )


@router.post("/synthesize", summary="Text to Speech (JSON Body, 长文本推荐)")
async def text_to_speech_body(req: TtsRequest):
    """
    文本转语音（JSON Body 方式）。

    与 `POST /tts` 功能完全相同，区别是参数通过 **JSON 请求体**传递，
    不受 URL 长度限制，适合长文本（接近 5000 字）场景。

    **请求体示例：**
    ```json
    {
      "text": "要合成的文本内容...",
      "voice": "zh-CN-XiaoxiaoNeural",
      "rate": "+0%",
      "pitch": "+0Hz",
      "volume": "+0%",
      "fallback": false
    }
    ```

    **响应：** 与 `POST /tts` 相同，返回音频流（MP3 或 WAV）。
    """
    return await tts_service.synthesize(
        text=req.text,
        voice=req.voice,
        rate=req.rate,
        pitch=req.pitch,
        volume=req.volume,
        use_fallback=req.fallback,
    )


@router.get("/voices", summary="List Chinese Voices")
async def list_voices():
    """List available Chinese voices from edge-tts."""
    try:
        voices = await tts_service.list_voices()
        return {
            "count": len(voices),
            "voices": [
                {
                    "name": v["ShortName"],
                    "gender": v["Gender"],
                    "locale": v["Locale"],
                    "voice_id": v["ShortName"],
                }
                for v in voices
            ],
        }
    except Exception as e:
        logger.error("Failed to list voices: {}", e)
        return JSONResponse(
            status_code=503,
            content={"error": f"Failed to list voices: {str(e)}"}
        )


@router.get("/health", summary="TTS Health Check")
async def tts_health():
    """Check TTS engine availability."""
    from app.services.model_manager import model_manager
    status = model_manager.status()
    return {
        "edge_tts": status["edge_tts"],
        "sherpa_tts": status["sherpa_tts"],
        "primary": "edge_tts" if status["edge_tts"] else "sherpa_tts",
        "fallback": "sherpa_tts" if status["sherpa_tts"] else None,
    }
