"""
Logger utility using loguru.
Configured for both console and file output.
"""

import sys
from pathlib import Path
from loguru import logger

# Remove default handler
logger.remove()

# Console output with color
logger.add(
    sys.stdout,
    level="INFO",
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    colorize=True,
)

# File output (rotate at 10 MB, keep 7 days)
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logger.add(
    log_dir / "voice_server_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8",
)

def get_logger(name: str = "voice_server"):
    """Get a logger instance with the given name."""
    return logger.bind(name=name)
