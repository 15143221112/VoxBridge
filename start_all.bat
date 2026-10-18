@echo off
chcp 65001 >nul
REM ============================================================
REM Voice & AI Services - All-in-One Start Script
REM
REM Starts:
REM   1. Embedding Server  (port 8080) - Qwen3-Embedding-0.6B
REM   2. Voice Server       (port 8090) - TTS / ASR / KWS / VAD
REM
REM Usage: Double-click this file, or run in cmd.
REM ============================================================

title Voice and AI Services Launcher

REM --- Local paths (script located in voice_server\) ---
set "BASE_DIR=%~dp0"
set "EMB_DIR=%BASE_DIR%..\Qwen3-Embedding-0.6B"
set "VOICE_DIR=%BASE_DIR%"
set "EMB_PY=d:\miniconda3\envs\qwenemb\python.exe"
set "VOICE_PY=%VOICE_DIR%.venv_conda\python.exe"

echo ============================================================
echo  Voice and AI Services - Starting All...
echo ============================================================
echo.

REM --- Check Python ---
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH. Install Python 3.11+ first.
    pause
    exit /b 1
)

REM ============================================================
REM 1. Embedding Server (port 8080)
REM ============================================================
echo [1/2] Embedding Server (port 8080)
echo       Script : %EMB_DIR%\embedding_server.py
echo       Python : qwenemb conda env (sentence_transformers)
echo       Model  : d:\model\Qwen3-Embedding-0.6B

netstat -ano | findstr ":8080 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo       [SKIP] Port 8080 already in use - service may already be running.
    echo.
) else (
    start "Embedding Server [8080]" cmd /c "cd /d "%EMB_DIR%" && "%EMB_PY%" embedding_server.py --port 8080 --api-key sk-zhkj-embedding"
    echo       [OK] Embedding Server started in new window.
    echo.
)

REM ============================================================
REM 2. Voice Server (port 8090)
REM ============================================================
echo [2/2] Voice Server (port 8090)
echo       Script : %VOICE_DIR%app\main.py
echo       Python : .venv_conda (sherpa-onnx, edge-tts, fastapi, uvicorn)
echo       Modules: TTS / ASR / KWS / VAD

netstat -ano | findstr ":8090 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo       [SKIP] Port 8090 already in use - service may already be running.
    echo.
) else (
    REM Check venv exists
    if not exist "%VOICE_PY%" (
        echo       [ERROR] Voice Server venv not found: %VOICE_PY%
        echo       Run: cd %VOICE_DIR%
        echo           conda create -p .venv_conda python=3.11 and pip install -r requirements.txt
        echo.
    ) else (
        start "Voice Server [8090]" cmd /c "cd /d "%VOICE_DIR%" && "%VOICE_PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8090 --workers 1"
        echo       [OK] Voice Server started in new window.
        echo.
    )
)

REM ============================================================
REM Summary
REM ============================================================
echo ============================================================
echo  All Services Started!
echo ============================================================
echo.
echo  Embedding Server  :  http://localhost:8080
echo    Health          :  http://localhost:8080/health
echo    Stats           :  http://localhost:8080/stats
echo    API             :  POST http://localhost:8080/v1/embeddings
echo    API Key         :  sk-zhkj-embedding
echo.
echo  Voice Server       :  http://localhost:8090
echo    API Docs         :  http://localhost:8090/docs
echo    Health           :  http://localhost:8090/health
echo  TTS              :  POST http://localhost:8090/tts/synthesize  (JSON Body, 长文本推荐)
echo  TTS (Query)      :  POST http://localhost:8090/tts             (短文本/浏览器直连)
echo  TTS Voices       :  GET  http://localhost:8090/tts/voices
echo    ASR              :  POST http://localhost:8090/asr
echo    ASR Stream       :  WS   http://localhost:8090/asr/stream
echo    KWS Check        :  POST http://localhost:8090/kws/check
echo    KWS Keywords     :  GET  http://localhost:8090/kws/keywords
echo    KWS Stream       :  WS   http://localhost:8090/kws/stream
echo.
echo  Test Page          :  %VOICE_DIR%test_voice.html
echo.
echo  To stop: close the service windows or use Task Manager.
echo ============================================================
echo.
pause
