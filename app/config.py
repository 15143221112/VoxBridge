"""
Configuration loader for the voice server.
Reads config.yaml and provides typed access via dataclasses.
"""

from pathlib import Path
from typing import Any, Optional
import yaml
from dataclasses import dataclass, field

from app.utils.logger import get_logger

logger = get_logger("config")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8090
    workers: int = 1
    log_level: str = "info"


@dataclass
class EdgeTtsConfig:
    enabled: bool = True
    default_voice: str = "zh-CN-XiaoxiaoNeural"
    default_rate: str = "+0%"
    default_pitch: str = "+0Hz"
    default_volume: str = "+0%"
    timeout: int = 10


@dataclass
class SherpaTtsConfig:
    enabled: bool = False
    model_dir: str = "models/tts/kokoro-multi-lang-v1_0"
    model_name: str = "model.onnx"
    tokens_name: str = "tokens.txt"
    voices_name: str = "voices.bin"
    data_dir: str = "espeak-ng-data"
    default_speaker: int = 0
    default_speed: float = 1.0
    timeout: int = 30


@dataclass
class SherpaAsrConfig:
    enabled: bool = False
    model_dir: str = "models/asr/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20"
    encoder_name: str = "encoder-epoch-99-avg-1.onnx"
    decoder_name: str = "decoder-epoch-99-avg-1.onnx"
    joiner_name: str = "joiner-epoch-99-avg-1.onnx"
    tokens_name: str = "tokens.txt"
    decoding_method: str = "greedy_search"
    num_threads: int = 2
    sample_rate: int = 16000


@dataclass
class SherpaKwsConfig:
    enabled: bool = False
    model_dir: str = "models/kws/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01"
    encoder_name: str = "encoder-epoch-99-avg-1-chunk-16-left-64.int8.onnx"
    decoder_name: str = "decoder-epoch-99-avg-1-chunk-16-left-64.int8.onnx"
    joiner_name: str = "joiner-epoch-99-avg-1-chunk-16-left-64.int8.onnx"
    tokens_name: str = "tokens.txt"
    keywords_file: str = "keywords.txt"
    keywords: str = "n ǐ h ǎo x iǎo zh ì @你好小智"
    keywords_threshold: float = 0.2
    keywords_score: float = 1.8
    num_threads: int = 2
    max_num_frames: int = 100
    sample_rate: int = 16000


@dataclass
class VadConfig:
    enabled: bool = False
    model_path: str = "models/vad/silero_vad.onnx"
    threshold: float = 0.5
    min_silence_duration_ms: int = 500
    speech_pad_ms: int = 200


@dataclass
class RoutingConfig:
    @dataclass
    class TtsRouting:
        primary: str = "edge_tts"
        fallback: str = "sherpa_tts"
        fallback_timeout: int = 10

    @dataclass
    class AsrRouting:
        primary: str = "sherpa_asr"
        fallback: Optional[str] = None

    @dataclass
    class KwsRouting:
        primary: str = "sherpa_kws"
        fallback: Optional[str] = None

    tts: TtsRouting = field(default_factory=TtsRouting)
    asr: AsrRouting = field(default_factory=AsrRouting)
    kws: KwsRouting = field(default_factory=KwsRouting)


@dataclass
class CorsConfig:
    allow_origins: list = field(default_factory=lambda: ["*"])
    allow_methods: list = field(default_factory=lambda: ["*"])
    allow_headers: list = field(default_factory=lambda: ["*"])


class Settings:
    """Global configuration singleton."""

    server: ServerConfig = ServerConfig()
    edge_tts: EdgeTtsConfig = EdgeTtsConfig()
    sherpa_tts: SherpaTtsConfig = SherpaTtsConfig()
    sherpa_asr: SherpaAsrConfig = SherpaAsrConfig()
    sherpa_kws: SherpaKwsConfig = SherpaKwsConfig()
    vad: VadConfig = VadConfig()
    routing: RoutingConfig = RoutingConfig()
    cors: CorsConfig = CorsConfig()

    @classmethod
    def load(cls, path: Path = None):
        """Load configuration from YAML file."""
        if path is None:
            path = CONFIG_PATH

        if not path.exists():
            logger.warning(f"Config file not found at {path}, using defaults")
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        inst = cls()

        # Server
        if server := data.get("server"):
            inst.server = ServerConfig(**server)

        # edge-tts
        if edge := data.get("edge_tts"):
            inst.edge_tts = EdgeTtsConfig(**edge)

        # Sherpa TTS
        if stts := data.get("sherpa_tts"):
            inst.sherpa_tts = SherpaTtsConfig(**stts)

        # Sherpa ASR
        if sasr := data.get("sherpa_asr"):
            inst.sherpa_asr = SherpaAsrConfig(**sasr)

        # Sherpa KWS
        if skws := data.get("sherpa_kws"):
            inst.sherpa_kws = SherpaKwsConfig(**skws)

        # VAD
        if vad := data.get("vad"):
            inst.vad = VadConfig(**vad)

        # Routing
        if routing := data.get("routing"):
            if tts_r := routing.get("tts"):
                inst.routing.tts = RoutingConfig.TtsRouting(**tts_r)
            if asr_r := routing.get("asr"):
                inst.routing.asr = RoutingConfig.AsrRouting(**asr_r)
            if kws_r := routing.get("kws"):
                inst.routing.kws = RoutingConfig.KwsRouting(**kws_r)

        # CORS
        if cors := data.get("cors"):
            inst.cors = CorsConfig(**cors)

        logger.info("Configuration loaded from {}", path)
        return inst

    def model_abs_path(self, relative_dir: str) -> Path:
        """Convert a relative model directory to absolute path."""
        p = Path(relative_dir)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p


settings = Settings.load()
