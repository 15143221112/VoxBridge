"""
Model Download Script for Voice Server

Downloads Sherpa-ONNX models:
  1. KWS  - sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01 (3.3MB)
  2. ASR  - sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20 (~350MB)
  3. TTS  - kokoro-multi-lang-v1_0 (~180MB)
  4. VAD  - silero_vad.onnx (~2MB)

Usage:
    python scripts/download_models.py           # Download all
    python scripts/download_models.py --kws     # Only KWS
    python scripts/download_models.py --asr     # Only ASR
    python scripts/download_models.py --tts      # Only TTS
    python scripts/download_models.py --vad      # Only VAD
    python scripts/download_models.py --check    # Check existing models
"""

import argparse
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

# Model URLs from k2-fsa/sherpa-onnx releases
MODEL_URLS = {
    "kws": {
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01.tar.bz2",
        "dir": MODELS_DIR / "kws" / "sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01",
        "size_mb": 3.3,
    },
    "asr": {
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2",
        "dir": MODELS_DIR / "asr" / "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20",
        "size_mb": 350,
    },
    "tts": {
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_0.tar.bz2",
        "dir": MODELS_DIR / "tts" / "kokoro-multi-lang-v1_0",
        "size_mb": 180,
    },
    "vad": {
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx",
        "dir": MODELS_DIR / "vad" / "silero_vad.onnx",
        "size_mb": 2,
    },
}


def download_with_progress(url: str, dest: Path):
    """Download a file with progress indication."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        print(f"  [skip] {dest.name} already exists ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
        return dest

    print(f"  [download] {url}")
    print(f"  [target] {dest}")

    # urllib download with progress
    def _progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 / total_size)
            mb_down = downloaded / 1024 / 1024
            mb_total = total_size / 1024 / 1024
            print(f"\r  [progress] {mb_down:.1f} / {mb_total:.1f} MB ({pct:.0f}%)", end="", flush=True)
        else:
            mb_down = downloaded / 1024 / 1024
            print(f"\r  [progress] {mb_down:.1f} MB", end="", flush=True)

    urllib.request.urlretrieve(url, str(dest), _progress)
    print()  # newline after progress
    print(f"  [done] {dest.name} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
    return dest


def extract_tarbz(archive: Path, extract_to: Path):
    """Extract a .tar.bz2 archive."""
    print(f"  [extract] {archive.name} -> {extract_to}")
    with tarfile.open(str(archive), "r:bz2") as tar:
        tar.extractall(path=str(extract_to))
    # Clean up archive
    archive.unlink()
    print(f"  [cleanup] removed {archive.name}")


def download_kws():
    """Download KWS model (3.3MB)."""
    print("\n[1/4] Downloading KWS model (Zipformer wenetspeech 3.3MB)...")
    cfg = MODEL_URLS["kws"]
    target_dir = cfg["dir"]

    if target_dir.exists() and (target_dir / "encoder-epoch-99-avg-1-chunk-16-left-64.int8.onnx").exists():
        print(f"  [skip] KWS model already exists at {target_dir}")
        return True

    # Download tar.bz2
    archive = MODELS_DIR / "kws" / Path(cfg["url"]).name
    download_with_progress(cfg["url"], archive)

    # Extract
    extract_to = MODELS_DIR / "kws"
    extract_tarbz(archive, extract_to)

    # Verify
    if (target_dir / "encoder-epoch-99-avg-1-chunk-16-left-64.int8.onnx").exists():
        print(f"  [ok] KWS model ready at {target_dir}")
        return True
    else:
        print(f"  [warn] encoder not found after extraction, check {extract_to}")
        return False


def download_asr():
    """Download ASR model (~350MB)."""
    print("\n[2/4] Downloading ASR model (Streaming Zipformer bilingual zh-en)...")
    cfg = MODEL_URLS["asr"]
    target_dir = cfg["dir"]

    if target_dir.exists() and (target_dir / "encoder-epoch-99-avg-1.onnx").exists():
        print(f"  [skip] ASR model already exists at {target_dir}")
        return True

    archive = MODELS_DIR / "asr" / Path(cfg["url"]).name
    download_with_progress(cfg["url"], archive)

    extract_to = MODELS_DIR / "asr"
    extract_tarbz(archive, extract_to)

    if (target_dir / "encoder-epoch-99-avg-1.onnx").exists():
        print(f"  [ok] ASR model ready at {target_dir}")
        return True
    else:
        print(f"  [warn] encoder not found after extraction, check {extract_to}")
        return False


def download_tts():
    """Download TTS model (~180MB)."""
    print("\n[3/4] Downloading TTS model (Kokoro multi-language v1.0)...")
    cfg = MODEL_URLS["tts"]
    target_dir = cfg["dir"]

    if target_dir.exists() and (target_dir / "model.onnx").exists():
        print(f"  [skip] TTS model already exists at {target_dir}")
        return True

    archive = MODELS_DIR / "tts" / Path(cfg["url"]).name
    download_with_progress(cfg["url"], archive)

    extract_to = MODELS_DIR / "tts"
    extract_tarbz(archive, extract_to)

    if (target_dir / "model.onnx").exists():
        print(f"  [ok] TTS model ready at {target_dir}")
        return True
    else:
        print(f"  [warn] model.onnx not found after extraction, check {extract_to}")
        return False


def download_vad():
    """Download VAD model (~2MB)."""
    print("\n[4/4] Downloading VAD model (Silero VAD)...")
    cfg = MODEL_URLS["vad"]
    target = cfg["dir"]

    if target.exists():
        print(f"  [skip] VAD model already exists at {target}")
        return True

    download_with_progress(cfg["url"], target)

    if target.exists():
        print(f"  [ok] VAD model ready at {target}")
        return True
    return False


def check_models():
    """Check which models are already downloaded."""
    print("\n=== Model Status Check ===\n")

    for name, cfg in MODEL_URLS.items():
        target = cfg["dir"]
        size_mb = cfg["size_mb"]
        if target.exists():
            actual_size = target.stat().st_size / 1024 / 1024 if target.is_file() else \
                sum(f.stat().st_size for f in target.rglob("*") if f.is_file()) / 1024 / 1024
            print(f"  [{name.upper():>4}] PRESENT  {actual_size:.1f} MB at {target}")
        else:
            print(f"  [{name.upper():>4}] MISSING  ~{size_mb} MB needed -> {target}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Download Sherpa-ONNX models for Voice Server"
    )
    parser.add_argument("--kws", action="store_true", help="Download KWS model only")
    parser.add_argument("--asr", action="store_true", help="Download ASR model only")
    parser.add_argument("--tts", action="store_true", help="Download TTS model only")
    parser.add_argument("--vad", action="store_true", help="Download VAD model only")
    parser.add_argument("--check", action="store_true", help="Check existing models only")
    args = parser.parse_args()

    if args.check:
        check_models()
        return

    # If no specific model requested, download all
    download_all = not (args.kws or args.asr or args.tts or args.vad)

    print("=" * 60)
    print("Voice Server - Model Downloader")
    print("=" * 60)

    results = {}

    if args.kws or download_all:
        results["kws"] = download_kws()
    if args.asr or download_all:
        results["asr"] = download_asr()
    if args.tts or download_all:
        results["tts"] = download_tts()
    if args.vad or download_all:
        results["vad"] = download_vad()

    print("\n" + "=" * 60)
    print("Download Summary")
    print("=" * 60)
    for model, ok in results.items():
        status = "SUCCESS" if ok else "FAILED"
        print(f"  {model.upper():>4}: {status}")

    # Check all models
    print()
    check_models()

    print("\nNext steps:")
    print("  1. Edit config.yaml and set enabled=true for downloaded models")
    print("  2. Run: run.bat (Windows) or python -m uvicorn app.main:app --port 8090")
    print("  3. Open http://localhost:8090/docs for API documentation")


if __name__ == "__main__":
    main()
