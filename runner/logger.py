"""
Structured logging utilities for the test framework.
Provides color-coded console output and file logging.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

from colorama import Fore, Style, init as colorama_init

import config

# Initialize colorama for Windows support
colorama_init(autoreset=True)


# ── Custom Formatter ──────────────────────────────────────────

class ColorFormatter(logging.Formatter):
    """Color-coded console log formatter."""
    
    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        reset = Style.RESET_ALL
        
        # Format level name with color
        record.levelname = f"{color}{record.levelname:<8}{reset}"
        
        # Format the message
        record.msg = f"{color}{record.msg}{reset}"
        
        return super().format(record)


class FileFormatter(logging.Formatter):
    """Clean file log formatter without ANSI codes."""
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


# ── Logger Setup ──────────────────────────────────────────────

_initialized = False


def setup_logging(level: str | None = None) -> logging.Logger:
    """
    Configure the root logger with console and file handlers.
    
    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
               Defaults to config.LOG_LEVEL.
               
    Returns:
        The configured root logger.
    """
    global _initialized
    
    if _initialized:
        return logging.getLogger("ai_test_framework")
    
    log_level = getattr(logging, level or config.LOG_LEVEL, logging.INFO)
    
    # Create framework logger
    logger = logging.getLogger("ai_test_framework")
    logger.setLevel(log_level)
    
    # Also set root logger for libraries
    root = logging.getLogger()
    root.setLevel(logging.WARNING)  # Suppress noisy library logs
    
    # ── Console Handler ────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console_fmt = ColorFormatter(
        fmt="%(asctime)s │ %(levelname)s │ %(message)s",
        datefmt="%H:%M:%S",
    )
    console.setFormatter(console_fmt)
    logger.addHandler(console)
    
    # ── File Handler ───────────────────────────────────────
    try:
        config.LOGS_DIR.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(
            config.LOG_FILE,
            mode="a",
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        file_handler.setFormatter(FileFormatter())
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not set up file logging: {e}")
    
    _initialized = True
    logger.debug("Logging initialized")
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger under the framework namespace.
    
    Args:
        name: Logger name (typically __name__).
        
    Returns:
        A configured child logger.
    """
    return logging.getLogger(f"ai_test_framework.{name}")
