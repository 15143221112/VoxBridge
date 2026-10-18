"""
Quick test script for Voice Server.
Tests all endpoints after starting the server.

Usage:
    1. Start server: run.bat
    2. In another terminal: python tests/test_server.py
"""

import asyncio
import json
import httpx
import struct

BASE_URL = "http://localhost:8090"
WS_BASE = "ws://localhost:8090"


async def test_health():
    """Test overall health check."""
    print("\n[1] Testing GET /health...")
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/health")
        print(f"  Status: {r.status_code}")
        print(f"  Body: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


async def test_tts():
    """Test TTS endpoint."""
    print("\n[2] Testing POST /tts...")
    async with httpx.AsyncClient(timeout=30) as client:
        # edge-tts primary
        r = await client.post(
            f"{BASE_URL}/tts",
            params={"text": "你好，欢迎使用语音助手。", "voice": "zh-CN-XiaoxiaoNeural"},
        )
        print(f"  Status: {r.status_code}")
        print(f"  Engine: {r.headers.get('X-TTS-Engine', 'unknown')}")
        print(f"  Content-Type: {r.headers.get('content-type', 'unknown')}")
        print(f"  Audio size: {len(r.content)} bytes ({len(r.content)/1024:.1f} KB)")

        # Check if audio is valid (starts with MP3 header or WAV header)
        if r.content[:4] == b'ID3\x03' or r.content[:2] == b'\xff\xfb':
            print("  Format: MP3 (edge-tts)")
        elif r.content[:4] == b'RIFF':
            print("  Format: WAV (sherpa-onnx)")
        else:
            print(f"  Format: Unknown (header={r.content[:4].hex()})")


async def test_tts_voices():
    """Test listing voices."""
    print("\n[3] Testing GET /tts/voices...")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{BASE_URL}/tts/voices")
        print(f"  Status: {r.status_code}")
        data = r.json()
        print(f"  Voice count: {data.get('count', 0)}")
        for v in data.get("voices", [])[:5]:
            print(f"    - {v['name']} ({v['gender']})")


async def test_kws_keywords():
    """Test listing keywords."""
    print("\n[4] Testing GET /kws/keywords...")
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/kws/keywords")
        print(f"  Status: {r.status_code}")
        print(f"  Body: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


async def test_kws_health():
    """Test KWS health."""
    print("\n[5] Testing GET /kws/health...")
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/kws/health")
        print(f"  Status: {r.status_code}")
        print(f"  Body: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


async def test_asr_health():
    """Test ASR health."""
    print("\n[6] Testing GET /asr/health...")
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/asr/health")
        print(f"  Status: {r.status_code}")
        print(f"  Body: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


async def test_root():
    """Test root endpoint."""
    print("\n[7] Testing GET /...")
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/")
        print(f"  Status: {r.status_code}")
        data = r.json()
        print(f"  Name: {data.get('name')}")
        print(f"  Version: {data.get('version')}")
        print(f"  Models: {json.dumps(data.get('models'), ensure_ascii=False)}")


async def test_ws_tts_asr():
    """Test WebSocket ASR streaming with TTS audio."""
    print("\n[8] Testing WebSocket /asr/stream (with TTS audio)...")
    try:
        import websockets
    except ImportError:
        print("  [skip] websockets not installed. Run: pip install websockets")
        return

    import numpy as np

    # First, generate TTS audio
    print("  Generating TTS audio for ASR test...")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/tts",
            params={"text": "你好小智，帮我打开水田闸门。"},
        )
        if r.status_code != 200:
            print(f"  [skip] TTS failed ({r.status_code}), skipping ASR test")
            return
        audio_data = r.content

    # Check if ASR is available
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/asr/health")
        if not r.json().get("sherpa_asr"):
            print("  [skip] ASR model not loaded, skipping WebSocket test")
            return

    # Convert MP3 to PCM for WebSocket
    print("  Converting audio to PCM...")
    try:
        import librosa
        import tempfile
        import os

        # Write MP3 to temp file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        samples, sr = librosa.load(tmp_path, sr=16000, mono=True)
        os.unlink(tmp_path)
        pcm = (samples * 32767).astype(np.int16).tobytes()

        # Send via WebSocket in chunks
        chunk_size = int(16000 * 0.5) * 2  # 0.5s of 16-bit PCM
        print(f"  Sending {len(pcm)} bytes of PCM in {chunk_size}-byte chunks...")

        async with websockets.connect(f"{WS_BASE}/asr/stream") as ws:
            for i in range(0, len(pcm), chunk_size):
                await ws.send(pcm[i:i+chunk_size])
                await asyncio.sleep(0.1)

                # Check for responses
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.2)
                    data = json.loads(msg)
                    if data.get("text"):
                        print(f"    [{'final' if data.get('is_final') else 'partial'}] {data['text']}")
                except asyncio.TimeoutError:
                    pass

            # Send stop
            await ws.send(json.dumps({"action": "stop"}))

            # Get final response
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(msg)
                if data.get("text"):
                    print(f"    [final] {data['text']}")
                else:
                    print(f"    [response] {data}")
            except asyncio.TimeoutError:
                print("    [timeout] No final response")

        print("  WebSocket ASR test done.")

    except ImportError:
        print("  [skip] librosa not installed, can't convert audio")


async def test_ws_kws():
    """Test WebSocket KWS streaming."""
    print("\n[9] Testing WebSocket /kws/stream...")
    try:
        import websockets
    except ImportError:
        print("  [skip] websockets not installed")
        return

    # Check if KWS is available
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/kws/health")
        if not r.json().get("sherpa_kws"):
            print("  [skip] KWS model not loaded, skipping WebSocket test")
            return

    import numpy as np

    # Generate "你好小智" TTS audio
    print("  Generating TTS audio for KWS test...")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/tts",
            params={"text": "你好小智", "voice": "zh-CN-XiaoxiaoNeural"},
        )
        if r.status_code != 200:
            print(f"  [skip] TTS failed ({r.status_code})")
            return
        audio_data = r.content

    # Convert to PCM
    try:
        import librosa
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        samples, sr = librosa.load(tmp_path, sr=16000, mono=True)
        os.unlink(tmp_path)
        pcm = (samples * 32767).astype(np.int16).tobytes()

        chunk_size = int(16000 * 0.5) * 2  # 0.5s
        print(f"  Sending {len(pcm)} bytes of PCM...")

        async with websockets.connect(f"{WS_BASE}/kws/stream") as ws:
            for i in range(0, len(pcm), chunk_size):
                await ws.send(pcm[i:i+chunk_size])
                await asyncio.sleep(0.1)

                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.2)
                    data = json.loads(msg)
                    if data.get("detected"):
                        print(f"    [DETECTED] keyword='{data.get('keyword')}'")
                    # else: heartbeat, don't print
                except asyncio.TimeoutError:
                    pass

            await ws.send(json.dumps({"action": "stop"}))

        print("  WebSocket KWS test done.")

    except ImportError:
        print("  [skip] librosa not installed")


async def main():
    print("=" * 60)
    print("Voice Server - Test Suite")
    print("=" * 60)

    await test_root()
    await test_health()
    await test_tts()
    await test_tts_voices()
    await test_kws_keywords()
    await test_kws_health()
    await test_asr_health()

    # WebSocket tests (require models)
    await test_ws_tts_asr()
    await test_ws_kws()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
