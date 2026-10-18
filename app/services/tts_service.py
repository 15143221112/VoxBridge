"""
TTS Service - Text to Speech with smart routing.

Primary:   edge-tts (Microsoft Azure Neural TTS, free, online)
Fallback:  Sherpa-ONNX Kokoro (offline, local)

Routing logic:
  1. Pre-flight: try to get first audio chunk from edge-tts (with timeout)
  2. If pre-flight succeeds, stream all audio to client (MP3)
  3. If edge-tts fails or times out, use Sherpa-ONNX Kokoro (WAV)
  4. If both unavailable, return 503
"""

import asyncio
import io
import time
from typing import Optional

import edge_tts
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.services.model_manager import model_manager
from app.utils.logger import get_logger

logger = get_logger("tts_service")


class TtsService:
    """TTS service with edge-tts primary and Sherpa-ONNX fallback."""

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        volume: Optional[str] = None,
        use_fallback: bool = False,
    ) -> StreamingResponse:
        """
        Convert text to speech.

        Args:
            text: Text to synthesize.
            voice: Voice name (e.g., "zh-CN-XiaoxiaoNeural").
            rate: Speech rate (e.g., "+10%", "-5%").
            pitch: Pitch (e.g., "+2Hz", "-1Hz").
            volume: Volume (e.g., "+20%", "-10%").
            use_fallback: If True, skip edge-tts and use Sherpa-ONNX directly.

        Returns:
            StreamingResponse with audio/mpeg (edge-tts) or audio/wav (sherpa-onnx).
        """
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        start = time.time()

        # Determine routing
        use_edge = settings.edge_tts.enabled and not use_fallback
        use_sherpa = settings.sherpa_tts.enabled

        v = voice or settings.edge_tts.default_voice
        r = rate or settings.edge_tts.default_rate
        p = pitch or settings.edge_tts.default_pitch
        vol = volume or settings.edge_tts.default_volume

        # ---- Edge-tts (online primary) ----
        if use_edge:
            try:
                communicate = edge_tts.Communicate(
                    text=text, voice=v, rate=r, pitch=p, volume=vol
                )
                stream = communicate.stream()

                # Pre-flight: try to get the first audio chunk with timeout
                # This verifies edge-tts connectivity before streaming to client
                first_chunk = None
                try:
                    first = await asyncio.wait_for(
                        stream.__anext__(),
                        timeout=settings.routing.tts.fallback_timeout,
                    )
                    if first["type"] == "audio":
                        first_chunk = first["data"]
                except StopAsyncIteration:
                    # No chunks at all (edge case, very short text)
                    pass

                logger.info("TTS via edge-tts: text='{}' voice={}", text[:50], v)

                async def _audio_stream():
                    """Stream remaining audio chunks after pre-flight."""
                    if first_chunk is not None:
                        yield first_chunk
                    async for chunk in stream:
                        if chunk["type"] == "audio":
                            yield chunk["data"]

                logger.info("TTS edge-tts streaming started in {:.2f}s",
                            time.time() - start)
                return StreamingResponse(
                    _audio_stream(),
                    media_type="audio/mpeg",
                    headers={
                        "X-TTS-Engine": "edge-tts",
                        "X-TTS-Voice": v,
                        "Cache-Control": "no-cache",
                    },
                )

            except asyncio.TimeoutError:
                logger.warning(
                    "edge-tts timed out after {}s, falling back to Sherpa-ONNX",
                    settings.routing.tts.fallback_timeout,
                )
            except Exception as e:
                logger.warning("edge-tts failed: {}, falling back to Sherpa-ONNX", e)

        # ---- Sherpa-ONNX (offline fallback) ----
        if use_sherpa and model_manager.tts_model is not None:
            try:
                logger.info("TTS via Sherpa-ONNX (offline): text='{}'", text[:50])
                audio_bytes = self._sherpa_tts(text)
                logger.info("TTS Sherpa-ONNX completed in {:.2f}s",
                            time.time() - start)
                return StreamingResponse(
                    io.BytesIO(audio_bytes),
                    media_type="audio/wav",
                    headers={
                        "X-TTS-Engine": "sherpa-onnx",
                        "Cache-Control": "no-cache",
                    },
                )
            except Exception as e:
                logger.error("Sherpa-ONNX TTS also failed: {}", e)

        # ---- All engines failed ----
        raise HTTPException(
            status_code=503,
            detail="All TTS engines unavailable. Check edge-tts connectivity and model files.",
        )

    def _sherpa_tts(self, text: str) -> bytes:
        """
        Generate WAV audio using Sherpa-ONNX Kokoro TTS (offline).

        Returns raw WAV bytes.
        """
        import soundfile as sf
        import numpy as np

        cfg = settings.sherpa_tts
        audio = model_manager.tts_model.generate(
            text,
            sid=cfg.default_speaker,
            speed=cfg.default_speed,
        )

        samples = np.array(audio.samples, dtype=np.float32)

        # Convert to WAV bytes
        buf = io.BytesIO()
        sf.write(buf, samples, audio.sample_rate, format="WAV", subtype="PCM_16")
        buf.seek(0)
        return buf.getvalue()

    async def list_voices(self) -> list:
        """List available edge-tts voices (Chinese)."""
        voices = await edge_tts.list_voices()
        return [v for v in voices if v["Locale"].startswith("zh-CN")]


tts_service = TtsService()
