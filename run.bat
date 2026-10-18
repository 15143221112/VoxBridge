@echo off
REM ============================================================
REM Voice Server - Windows Start Script
REM Run: edge-tts + Sherpa-ONNX voice service on port 8090
REM ============================================================

cd /d "%~dp0"

echo ============================================================
echo  Voice Server - Starting...
echo  Port: 8090
echo  TTS: edge-tts (online) + Sherpa-ONNX (offline fallback)
echo  ASR: Sherpa-ONNX streaming zipformer (offline)
echo  KWS: Sherpa-ONNX zipformer 3.3M (offline)
echo ============================================================
echo.

REM Check virtual environment (.venv_conda is the working env)
if not exist ".venv_conda\python.exe" (
    echo [ERROR] Virtual environment not found: .venv_conda
    echo [SETUP] Run: conda create -p .venv_conda python=3.11
    echo [SETUP]      .venv_conda\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)
set "PYTHON=.venv_conda\python.exe"

REM Check models (optional, just info)
if not exist "models\kws" (
    echo [INFO] KWS model not found. Run: python scripts\download_models.py --kws
    echo [INFO] Or skip KWS and use TTS/ASR only.
    echo.
)

if not exist "models\asr" (
    echo [INFO] ASR model not found. Run: python scripts\download_models.py --asr
    echo.
)

if not exist "models\tts" (
    echo [INFO] TTS model not found. Run: python scripts\download_models.py --tts
    echo [INFO] edge-tts will be used as primary TTS (no offline fallback)
    echo.
)

echo [START] Voice Server launching at http://localhost:8090
echo [DOCS] API documentation at http://localhost:8090/docs
echo.

"%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8090 --workers 1

pause
