# 🎙️ xh-voice-server

> A ready-to-use **voice service middleware**: TTS (text-to-speech) + ASR (speech-to-text) + KWS (wake-word detection). Hybrid online/offline with smart fallback — zero API keys, zero cost.

[中文](README.md) · [Changelog](CHANGELOG.md)

---

## ✨ Highlights

- **All-in-one voice**: TTS / ASR / KWS in a single service, reachable via HTTP + WebSocket.
- **Hybrid online/offline with smart fallback**: TTS prefers `edge-tts` (Microsoft Azure Neural TTS, **free, no API key**); automatically falls back to local Sherpa-ONNX Kokoro on timeout (10s) or network failure — **service never goes down**.
- **Fully offline ASR / KWS**: speech recognition and wake-word detection run locally, **sensitive audio never leaves your server**. Bilingual (Chinese/English) streaming supported.
- **Zero-cost start**: open-source models only (KWS 3.3MB, ASR ~350MB); the online TTS engine needs no download or key.
- **Custom wake words without retraining**: edit `keywords` in `config.yaml` to define any wake word.
- **Real-time streaming**: WebSocket enables **speak-as-you-type** ASR and **listen-while-speaking** KWS.
- **Complete health checks**: overall `/health` plus per-engine `/tts/health`, `/asr/health`, `/kws/health`.
- **Cross-platform**: Windows (`.bat` one-click) + Linux (systemd unit / `.sh`). Native venv, no Docker required.
- **Models downloaded on demand**: `scripts/download_models.py` fetches per module.

---

## 📦 Features

| Capability | Engine | Online/Offline | Description |
|---|---|---|---|
| **TTS** | edge-tts | online | Microsoft Azure Neural TTS, free, 8 Chinese/dialect voices |
| **TTS fallback** | Sherpa-ONNX Kokoro | offline | Auto-switch on timeout/disconnect, local CPU inference |
| **ASR** | Sherpa-ONNX Streaming Zipformer | offline | Bilingual, file upload + WebSocket realtime stream |
| **KWS** | Sherpa-ONNX Zipformer 3.3M | offline | 3.3MB only, custom keywords (txt config, no retrain) |
| **VAD** | Silero VAD | offline | Optional, for ASR denoise/split |
| **Streaming ASR** | WebSocket | — | `WS /asr/stream` |
| **Streaming KWS** | WebSocket | — | `WS /kws/stream` |
| **Voice tuning** | edge-tts | — | rate / pitch / volume / voice |

---

## 🚀 Quick Start

### Windows

```bat
cd xh-voice-server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python scripts/download_models.py --kws    :: 3.3MB
python scripts/download_models.py --asr    :: ~350MB
python scripts/download_models.py --tts    :: ~180MB (offline fallback)

:: edit config.yaml: set enabled: true for downloaded models
run.bat
```

> The **edge-tts online engine needs no model download** — install dependencies and it works out of the box.

### Linux (systemd)

```bash
sudo mkdir -p /opt/voice_server && sudo chown $USER:$USER /opt/voice_server
cd /opt/voice_server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_models.py --asr --kws --tts

sudo cp deploy/voice-server.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now voice-server

curl -s http://127.0.0.1:8090/health      # {"status":"ok",...}
```

---

## 🔌 API

| Endpoint | Method | Description |
|---|---|---|
| `/tts?text=你好世界` | POST | TTS synthesize (MP3) |
| `/tts?text=...&voice=...&rate=+10%` | POST | TTS with voice/rate |
| `/tts?text=...&fallback=true` | POST | Force offline TTS |
| `/tts/voices` | GET | List available voices |
| `/asr` | POST | File upload recognition (multipart) |
| `/asr/stream` | WS | Realtime streaming ASR (PCM 16k mono) |
| `/kws/check` | POST | Check audio for keywords |
| `/kws/keywords` | GET | List configured keywords |
| `/kws/stream` | WS | Realtime keyword spotting |
| `/health` | GET | Overall health |
| `/docs` | GET | Swagger UI |

---

## 📁 Structure

```
xh-voice-server/
├── app/
│   ├── main.py              # FastAPI entry
│   ├── config.py            # YAML config loader
│   ├── routers/             # tts.py / asr.py / kws.py
│   ├── services/            # service logic + model_manager
│   └── utils/logger.py      # loguru
├── scripts/download_models.py
├── tests/
│   ├── test_server.py
│   └── test_tts_quality.py
├── deploy/
│   ├── voice-server.service
│   └── README-Linux.md
├── config.yaml
├── requirements.txt
├── run.bat / run.sh
└── README.md
```

---

## 🛠 Tech Stack

Python 3.11+ · FastAPI 0.115.6 · uvicorn 0.34.0 · edge-tts ≥ 7.2.8 · sherpa-onnx 1.11.4 · numpy 1.26.4 · librosa 0.10.2

> **edge-tts version**: must be ≥ 7.2.8 (Chromium 143+). Older 7.0.x versions get 403 from Microsoft's WSS endpoint.

---

## 📄 License

[MIT](LICENSE) © 2026 xh-voice-server contributors
