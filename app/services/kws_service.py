"""
KWS Service - Keyword Spotting (Wake Word Detection) using Sherpa-ONNX.

Provides:
  1. POST /kws/check  - Check a chunk of audio for keywords
  2. WS  /kws/stream  - Real-time keyword spotting via WebSocket

Uses 3.3MB Zipformer wenetspeech model.
Keywords are defined in config.yaml (customizable without retraining).
"""

import json
import time
import numpy as np
from typing import Optional

from app.config import settings
from app.services.model_manager import model_manager
from app.utils.logger import get_logger

logger = get_logger("kws_service")


class KwsService:
    """Keyword spotting service using Sherpa-ONNX Zipformer (3.3MB)."""

    def check_audio(self, samples: np.ndarray) -> dict:
        """
        Check a chunk of audio for wake words.

        Args:
            samples: int16 PCM samples at 16kHz.

        Returns:
            {
                "detected": bool,
                "keyword": str or None,
                "keyword_index": int or None,
                "timestamp": float
            }
        """
        if not settings.sherpa_kws.enabled or model_manager.kws_model is None:
            return {
                "detected": False,
                "keyword": None,
                "keyword_index": None,
                "timestamp": time.time(),
                "error": "KWS engine not available"
            }

        try:
            import sherpa_onnx

            spotter = model_manager.kws_model
            stream = spotter.create_stream()

            # Process audio - convert int16 to float32 normalized [-1, 1]
            samples_f32 = samples.astype(np.float32) / 32768.0
            stream.accept_waveform(
                settings.sherpa_kws.sample_rate,
                samples_f32
            )

            # Add tail padding (~0.66s of silence) to let decoder finalize keyword
            tail_paddings = np.zeros(
                int(0.66 * settings.sherpa_kws.sample_rate),
                dtype=np.float32
            )
            stream.accept_waveform(settings.sherpa_kws.sample_rate, tail_paddings)
            stream.input_finished()

            # Decode and check for keyword during the decode loop
            keyword = None
            while spotter.is_ready(stream):
                spotter.decode_stream(stream)
                result = spotter.get_result(stream)
                if result:
                    keyword = result
                    break

            if keyword:
                result = {
                    "detected": True,
                    "keyword": keyword,
                    "keyword_index": 0,
                    "timestamp": time.time()
                }
                logger.info("KWS detected keyword: '{}'", keyword)
                return result

            return {
                "detected": False,
                "keyword": None,
                "keyword_index": None,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error("KWS check error: {}", e)
            return {
                "detected": False,
                "keyword": None,
                "keyword_index": None,
                "timestamp": time.time(),
                "error": str(e)
            }

    def get_keywords(self) -> list:
        """Get list of configured keywords."""
        keywords_text = settings.sherpa_kws.keywords.strip()
        keywords = []
        for line in keywords_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Format: <pinyin_tokens> @<display_name>
            # e.g., "n ǐ h ǎo x iǎo zh ì @你好小智"
            parts = line.rsplit("@", 1)
            if len(parts) == 2:
                # After @ is the display name (Chinese keyword)
                word = parts[1].strip()
            else:
                # No @ separator, use the whole line
                word = parts[0].strip()
            threshold = getattr(settings.sherpa_kws, 'keywords_threshold', 0.2) or 0.2
            keywords.append({
                "keyword": word,
                "threshold": threshold,
            })
        return keywords

    async def stream_detect(self, websocket):
        """
        WebSocket streaming KWS.

        Client sends binary audio chunks (16-bit PCM, 16kHz, mono).
        Server responds with JSON when a keyword is detected:
          {"detected": true, "keyword": "...", "timestamp": 1234567890.0}

        Protocol:
          - Client sends audio chunks as binary messages
          - Client sends {"action": "stop"} to end session
          - Server sends {"detected": true/false, ...} for each chunk
        """
        if not settings.sherpa_kws.enabled or model_manager.kws_model is None:
            await websocket.send_json({
                "error": "KWS engine not available. Download model first."
            })
            await websocket.close()
            return

        import sherpa_onnx

        spotter = model_manager.kws_model
        stream = spotter.create_stream()
        sample_rate = settings.sherpa_kws.sample_rate

        logger.info("WebSocket KWS session started")

        try:
            while True:
                msg = await websocket.receive()

                if msg.get("type") == "websocket.disconnect":
                    break

                if "text" in msg:
                    data = json.loads(msg["text"])
                    if data.get("action") == "stop":
                        await websocket.send_json({
                            "detected": False,
                            "message": "session_ended"
                        })
                        break
                    if data.get("action") == "reset":
                        spotter.reset_stream(stream)
                        await websocket.send_json({
                            "detected": False,
                            "message": "stream_reset"
                        })
                        continue
                    continue

                if "bytes" in msg and msg["bytes"] is not None:
                    raw = msg["bytes"]
                    samples = np.frombuffer(raw, dtype=np.int16)
                    # Convert to float32 normalized [-1, 1]
                    samples_f32 = samples.astype(np.float32) / 32768.0

                    stream.accept_waveform(sample_rate, samples_f32)

                    while spotter.is_ready(stream):
                        spotter.decode_stream(stream)

                    # Check for keyword detection (sherpa-onnx 1.13.4: use get_result)
                    keyword = spotter.get_result(stream)
                    if keyword:
                        logger.info("KWS stream detected: '{}'", keyword)
                        await websocket.send_json({
                            "detected": True,
                            "keyword": keyword,
                            "timestamp": time.time()
                        })
                        # Reset after detection
                        spotter.reset_stream(stream)
                    else:
                        # Send heartbeat
                        await websocket.send_json({
                            "detected": False,
                            "timestamp": time.time()
                        })

        except Exception as e:
            logger.error("WebSocket KWS error: {}", e)
            await websocket.send_json({"error": str(e)})
        finally:
            logger.info("WebSocket KWS session ended")
            await websocket.close()


kws_service = KwsService()
