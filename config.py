"""
Configuration management for the AI Test Case Generation Framework.
Loads settings from environment variables and provides defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# ── Project Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
GENERATED_TESTS_DIR = BASE_DIR / "generated_tests"
LOGS_DIR = BASE_DIR / "logs"
SAMPLE_SPECS_DIR = BASE_DIR / "sample_specs"

# Ensure output directories exist
GENERATED_TESTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ── LLM Configuration ─────────────────────────────────────────
LLM_PROVIDER = "gemini"
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.0-flash")

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# LLM parameters
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))

# ── Logging ────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = LOGS_DIR / "framework.log"

# ── Test Runner ────────────────────────────────────────────────
PYTEST_ARGS = [
    "-v",
    "--tb=short",
    f"--html={LOGS_DIR / 'report.html'}",
    "--self-contained-html",
]


def validate_config():
    """Validate that required configuration is present."""
    if not GOOGLE_API_KEY:
        raise EnvironmentError(
            "Configuration error:\n  • GOOGLE_API_KEY is required for Gemini LLM."
        )


def get_config_summary() -> dict:
    """Return a summary of the current configuration (safe to log)."""
    return {
        "llm_provider": LLM_PROVIDER,
        "model_name": MODEL_NAME,
        "temperature": LLM_TEMPERATURE,
        "generated_tests_dir": str(GENERATED_TESTS_DIR),
        "logs_dir": str(LOGS_DIR),
        "log_level": LOG_LEVEL,
    }
