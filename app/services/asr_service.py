"""
ASR Service - Automatic Speech Recognition using Sherpa-ONNX.

Provides:
  1. POST /asr  - Batch ASR from audio file upload (WAV/MP3)
  2. WS  /asr/stream - Real-time streaming ASR via WebSocket

Uses streaming Zipformer bilingual (zh-en) model.
"""

import io
import json
import time
import tempfile
import os
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import UploadFile, HTTPException

from app.config import settings
from app.services.model_manager import model_manager
from app.utils.logger import get_logger

logger = get_logger("asr_service")


class AsrService:
    """ASR service using Sherpa-ONNX streaming Zipformer."""

    def recognize_file(self, audio_file: UploadFile) -> dict:
        """
        Recognize speech from an uploaded audio file.

        Args:
            audio_file: WAV or MP3 file upload.

        Returns:
            {"text": "recognized text", "confidence": 0.0, "duration_ms": 0}
        """
        if not settings.sherpa_asr.enabled or model_manager.asr_model is None:
            raise HTTPException(
                status_code=503,
                detail="ASR engine not available. Download Sherpa-ONNX ASR models first."
            )

        start = time.time()

        # Read audio file
        content = audio_file.file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty audio file")

        # Save to temp file for librosa to read
        suffix = Path(audio_file.filename or "audio.wav").suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Load audio
            import librosa
            samples, sr = librosa.load(
                tmp_path,
                sr=settings.sherpa_asr.sample_rate,
                mono=True,
            )
            samples = (samples * 32767).astype(np.int16)
            duration_ms = int(len(samples) / sr * 1000)

            logger.info("ASR file loaded: {} samples, {}ms, sr={}",
                        len(samples), duration_ms, sr)

            # Recognize
            text = self._recognize_samples(samples)

            elapsed = time.time() - start
            logger.info("ASR recognized in {:.2f}s: '{}'", elapsed, text)

            return {
                "text": text,
                "confidence": 0.0,  # Streaming ASR doesn't provide confidence
                "duration_ms": duration_ms,
                "engine": "sherpa-onnx-streaming-zipformer-bilingual",
            }

        except Exception as e:
            logger.error("ASR file recognition error: {}", e)
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            os.unlink(tmp_path)

    def _recognize_samples(self, samples: np.ndarray) -> str:
        """
        Recognize speech from 16-bit PCM samples.

        Uses online (streaming) recognizer which processes samples in chunks.
        """
        recognizer = model_manager.asr_model
        stream = recognizer.create_stream()

        # Convert int16 to float32 normalized [-1, 1] for sherpa-onnx
        samples_f32 = samples.astype(np.float32) / 32768.0

        # Process in chunks of 0.5s
        chunk_size = int(settings.sherpa_asr.sample_rate * 0.5)
        text_parts = []

        for i in range(0, len(samples_f32), chunk_size):
            chunk = samples_f32[i:i + chunk_size]
            stream.accept_waveform(settings.sherpa_asr.sample_rate, chunk)

            while recognizer.is_ready(stream):
                recognizer.decode_stream(stream)

            if recognizer.is_endpoint(stream):
                text = recognizer.get_result(stream)
                if text:
                    text_parts.append(text)
                recognizer.reset(stream)

        # Get final result
        text = recognizer.get_result(stream)
        if text:
            text_parts.append(text)

        return "".join(text_parts).strip()

    async def stream_recognize(self, websocket):
        """
        WebSocket streaming ASR.

        Client sends binary audio chunks (16-bit PCM, 16kHz, mono).
        Server responds with JSON: {"text": "...", "is_final": bool}

        Protocol:
          - Client sends audio chunks as binary messages
          - Client sends {"action": "stop"} to end session
          - Server sends {"text": "...", "is_final": false} for partial results
          - Server sends {"text": "...", "is_final": true} on endpoint detection
        """
        if not settings.sherpa_asr.enabled or model_manager.asr_model is None:
            await websocket.send_json({
                "error": "ASR engine not available"
            })
            await websocket.close()
            return

        import sherpa_onnx

        recognizer = model_manager.asr_model
        stream = recognizer.create_stream()

        sample_rate = settings.sherpa_asr.sample_rate
        logger.info("WebSocket ASR session started")

        try:
            while True:
                msg = await websocket.receive()

                if msg.get("type") == "websocket.disconnect":
                    break

                if "text" in msg:
                    data = json.loads(msg["text"])
                    if data.get("action") == "stop":
                        # Final result
                        text = recognizer.get_result(stream)
                        if text:
                            await websocket.send_json({
                                "text": text,
                                "is_final": True,
                                "reason": "user_stop"
                            })
                        break
                    continue

                if "bytes" in msg and msg["bytes"] is not None:
                    raw = msg["bytes"]
                    # Assume 16-bit PCM, 16kHz, mono
                    samples = np.frombuffer(raw, dtype=np.int16)
                    # Convert to float32 normalized [-1, 1]
                    samples_f32 = samples.astype(np.float32) / 32768.0
                    stream.accept_waveform(sample_rate, samples_f32)

                    while recognizer.is_ready(stream):
                        recognizer.decode_stream(stream)

                    if recognizer.is_endpoint(stream):
                        text = recognizer.get_result(stream)
                        if text:
                            await websocket.send_json({
                                "text": text,
                                "is_final": True,
                                "reason": "endpoint"
                            })
                        recognizer.reset(stream)
                    else:
                        # Partial result
                        text = recognizer.get_result(stream)
                        if text:
                            await websocket.send_json({
                                "text": text,
                                "is_final": False,
                                "reason": "partial"
                            })

        except Exception as e:
            logger.error("WebSocket ASR error: {}", e)
            await websocket.send_json({"error": str(e)})
        finally:
            logger.info("WebSocket ASR session ended")
            await websocket.close()


asr_service = AsrService()
