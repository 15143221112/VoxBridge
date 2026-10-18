#!/bin/bash
# ============================================================
# Voice Server - Linux Start Script
# Run: edge-tts + Sherpa-ONNX voice service on port 8090
# ============================================================

set -e

# Switch to script directory
cd "$(dirname "$0")"

echo "============================================================"
echo " Voice Server - Starting..."
echo " Port: 8090"
echo " TTS: edge-tts (online) + Sherpa-ONNX (offline fallback)"
echo " ASR: Sherpa-ONNX streaming zipformer (offline)"
echo " KWS: Sherpa-ONNX zipformer 3.3M (offline)"
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found. Install Python 3.10+ first."
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  CentOS/RHEL:   sudo dnf install python3 python3-devel"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[INFO] Python version: $PYTHON_VERSION"

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo "[SETUP] Creating virtual environment..."
    python3 -m venv .venv
    echo "[SETUP] Installing dependencies..."
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
else
    echo "[INFO] Virtual environment found."
fi

# Activate venv
source .venv/bin/activate

# Check models (optional, just info)
if [ ! -d "models/kws" ]; then
    echo "[INFO] KWS model not found. Run: python scripts/download_models.py --kws"
    echo "[INFO] Or skip KWS and use TTS/ASR only."
    echo ""
fi

if [ ! -d "models/asr" ]; then
    echo "[INFO] ASR model not found. Run: python scripts/download_models.py --asr"
    echo ""
fi

if [ ! -d "models/tts" ]; then
    echo "[INFO] TTS model not found. Run: python scripts/download_models.py --tts"
    echo "[INFO] edge-tts will be used as primary TTS (no offline fallback)"
    echo ""
fi

echo "[START] Voice Server launching at http://0.0.0.0:8090"
echo "[DOCS] API documentation at http://localhost:8090/docs"
echo ""

python -m uvicorn app.main:app --host 0.0.0.0 --port 8090 --workers 1
