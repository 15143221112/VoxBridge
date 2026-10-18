"""
Model Manager - Loads and manages Sherpa-ONNX models for TTS, ASR, KWS.
Models are loaded lazily on first use to avoid long startup times.
Compatible with sherpa-onnx 1.13.4 API.
"""

from pathlib import Path
from typing import Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("model_manager")

# Sherpa-ONNX is imported lazily to avoid hard dependency at startup
_sherpa = None


def _import_sherpa():
    """Import sherpa-onnx lazily."""
    global _sherpa
    if _sherpa is None:
        try:
            import sherpa_onnx
            _sherpa = sherpa_onnx
            logger.info("sherpa-onnx imported successfully, version={}",
                        getattr(sherpa_onnx, "__version__", "unknown"))
        except ImportError:
            logger.error("sherpa-onnx not installed. Run: pip install sherpa-onnx")
            raise
    return _sherpa


class ModelManager:
    """Singleton manager for all Sherpa-ONNX models."""

    _instance: Optional["ModelManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._tts_model = None
        self._asr_model = None
        self._kws_model = None
        self._vad_model = None

    # ----------------------------------------------------------------
    # TTS Model (Kokoro multi-language)
    # ----------------------------------------------------------------
    @property
    def tts_model(self):
        if self._tts_model is None and settings.sherpa_tts.enabled:
            self._load_tts_model()
        return self._tts_model

    def _load_tts_model(self):
        """Load offline TTS model (Kokoro multi-language)."""
        try:
            sherpa = _import_sherpa()
            cfg = settings.sherpa_tts
            model_dir = settings.model_abs_path(cfg.model_dir)
            model_path = model_dir / cfg.model_name
            tokens_path = model_dir / cfg.tokens_name
            voices_path = model_dir / cfg.voices_name
            data_dir = model_dir / cfg.data_dir

            if not model_path.exists():
                logger.warning("TTS model not found at {}. TTS fallback disabled. "
                               "Run scripts/download_models.py first.", model_path)
                return

            logger.info("Loading Sherpa-ONNX TTS model from {}", model_dir)

            # Build lexicon path (comma-separated for multi-lang model)
            lexicon_parts = []
            for lex_name in ["lexicon-zh.txt", "lexicon-us-en.txt"]:
                lex_path = model_dir / lex_name
                if lex_path.exists():
                    lexicon_parts.append(str(lex_path))
            lexicon = ",".join(lexicon_parts)

            # Build rule_fsts for text normalization
            rule_fst_parts = []
            for fst_name in ["date-zh.fst", "number-zh.fst", "phone-zh.fst"]:
                fst_path = model_dir / fst_name
                if fst_path.exists():
                    rule_fst_parts.append(str(fst_path))
            rule_fsts = ",".join(rule_fst_parts)

            # Build dict_dir path if it exists
            dict_dir = model_dir / "dict"
            dict_dir_str = str(dict_dir) if dict_dir.exists() else ""

            kokoro_config = sherpa.OfflineTtsKokoroModelConfig(
                model=str(model_path),
                voices=str(voices_path),
                tokens=str(tokens_path),
                lexicon=lexicon,
                data_dir=str(data_dir),
                dict_dir=dict_dir_str,
            )

            model_config = sherpa.OfflineTtsModelConfig(
                kokoro=kokoro_config,
                num_threads=1,
                debug=False,
                provider="cpu",
            )

            tts_config = sherpa.OfflineTtsConfig(
                model=model_config,
                rule_fsts=rule_fsts,
                max_num_sentences=2,
            )

            self._tts_model = sherpa.OfflineTts(tts_config)
            logger.info("Sherpa-ONNX TTS model loaded. num_speakers={}, sample_rate={}",
                        self._tts_model.num_speakers, self._tts_model.sample_rate)

        except Exception as e:
            logger.error("Failed to load TTS model: {}", e)
            self._tts_model = None

    # ----------------------------------------------------------------
    # ASR Model (Streaming Zipformer bilingual zh-en)
    # ----------------------------------------------------------------
    @property
    def asr_model(self):
        if self._asr_model is None and settings.sherpa_asr.enabled:
            self._load_asr_model()
        return self._asr_model

    def _load_asr_model(self):
        """Load offline ASR model (streaming zipformer bilingual)."""
        try:
            sherpa = _import_sherpa()
            cfg = settings.sherpa_asr
            model_dir = settings.model_abs_path(cfg.model_dir)
            encoder_path = model_dir / cfg.encoder_name
            decoder_path = model_dir / cfg.decoder_name
            joiner_path = model_dir / cfg.joiner_name
            tokens_path = model_dir / cfg.tokens_name

            if not encoder_path.exists():
                logger.warning("ASR model not found at {}. ASR disabled. "
                               "Run scripts/download_models.py first.", encoder_path)
                return

            logger.info("Loading Sherpa-ONNX ASR model from {}", model_dir)

            # Use factory method from_transducer (sherpa-onnx 1.13.4 API)
            self._asr_model = sherpa.OnlineRecognizer.from_transducer(
                tokens=str(tokens_path),
                encoder=str(encoder_path),
                decoder=str(decoder_path),
                joiner=str(joiner_path),
                num_threads=cfg.num_threads,
                decoding_method=cfg.decoding_method,
                enable_endpoint_detection=True,
            )
            logger.info("Sherpa-ONNX ASR model loaded (streaming zipformer bilingual)")

        except Exception as e:
            logger.error("Failed to load ASR model: {}", e)
            self._asr_model = None

    # ----------------------------------------------------------------
    # KWS Model (Zipformer keyword spotting, 3.3MB)
    # ----------------------------------------------------------------
    @property
    def kws_model(self):
        if self._kws_model is None and settings.sherpa_kws.enabled:
            self._load_kws_model()
        return self._kws_model

    def _load_kws_model(self):
        """Load offline KWS model (zipformer keyword spotting, 3.3MB)."""
        try:
            sherpa = _import_sherpa()
            cfg = settings.sherpa_kws
            model_dir = settings.model_abs_path(cfg.model_dir)
            encoder_path = model_dir / cfg.encoder_name
            decoder_path = model_dir / cfg.decoder_name
            joiner_path = model_dir / cfg.joiner_name
            tokens_path = model_dir / cfg.tokens_name
            keywords_path = model_dir / cfg.keywords_file

            if not encoder_path.exists():
                logger.warning("KWS model not found at {}. KWS disabled. "
                               "Run scripts/download_models.py first.", encoder_path)
                return

            logger.info("Loading Sherpa-ONNX KWS model from {}", model_dir)

            # Write keywords file only if it doesn't exist
            # (keywords must be in pinyin token format, use scripts/generate_keywords.py to create)
            if not keywords_path.exists():
                keywords_path.parent.mkdir(parents=True, exist_ok=True)
                keywords_path.write_text(cfg.keywords, encoding="utf-8")
                logger.info("Keywords file written to {}", keywords_path)
            else:
                logger.info("Using existing keywords file at {}", keywords_path)

            # sherpa-onnx 1.13.4: KeywordSpotter takes direct parameters
            self._kws_model = sherpa.KeywordSpotter(
                tokens=str(tokens_path),
                encoder=str(encoder_path),
                decoder=str(decoder_path),
                joiner=str(joiner_path),
                keywords_file=str(keywords_path),
                num_threads=cfg.num_threads,
                keywords_threshold=getattr(cfg, 'keywords_threshold', 0.2) or 0.2,
                keywords_score=getattr(cfg, 'keywords_score', 1.8) or 1.8,
            )
            logger.info("Sherpa-ONNX KWS model loaded (3.3M wenetspeech)")

        except Exception as e:
            logger.error("Failed to load KWS model: {}", e)
            self._kws_model = None

    # ----------------------------------------------------------------
    # VAD Model (Silero VAD)
    # ----------------------------------------------------------------
    @property
    def vad_model(self):
        if self._vad_model is None and settings.vad.enabled:
            self._load_vad_model()
        return self._vad_model

    def _load_vad_model(self):
        """Load Silero VAD model."""
        try:
            sherpa = _import_sherpa()
            cfg = settings.vad
            model_path = settings.model_abs_path(cfg.model_path)

            if not model_path.exists():
                logger.warning("VAD model not found at {}. VAD disabled.", model_path)
                return

            logger.info("Loading Silero VAD from {}", model_path)

            # sherpa-onnx 1.13.4: SileroVadModelConfig uses seconds, not ms
            # min_silence_duration: 500ms -> 0.5s
            silero_config = sherpa.SileroVadModelConfig(
                model=str(model_path),
                threshold=cfg.threshold,
                min_silence_duration=cfg.min_silence_duration_ms / 1000.0,
            )

            vad_config = sherpa.VadModelConfig(
                silero_vad=silero_config,
                sample_rate=16000,
                num_threads=1,
                provider="cpu",
            )

            # VadModel uses static factory method create()
            self._vad_model = sherpa.VadModel.create(vad_config)
            logger.info("Silero VAD loaded")

        except Exception as e:
            logger.error("Failed to load VAD model: {}", e)
            self._vad_model = None

    # ----------------------------------------------------------------
    # Status helpers
    # ----------------------------------------------------------------
    def status(self) -> dict:
        """Return model loading status."""
        return {
            "edge_tts": settings.edge_tts.enabled,
            "sherpa_tts": settings.sherpa_tts.enabled and self._tts_model is not None,
            "sherpa_asr": settings.sherpa_asr.enabled and self._asr_model is not None,
            "sherpa_kws": settings.sherpa_kws.enabled and self._kws_model is not None,
            "vad": settings.vad.enabled and self._vad_model is not None,
        }


model_manager = ModelManager()
