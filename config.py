"""
Central config — import this everywhere instead of reading os.environ directly.
All secrets come from .env; all structural constants live here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Secrets (required) ---
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]

# Only messages from this chat ID are processed; everything else is silently dropped.
ALLOWED_CHAT_ID: int = int(os.environ["ALLOWED_CHAT_ID"])

# --- Model names ---
# Fast/cheap model for routing and conversational replies.
GEMINI_FAST_MODEL: str = os.getenv("GEMINI_FAST_MODEL", "gemini-2.5-flash-lite-preview-06-17")
# Stronger model reserved for digests and complex reasoning (plug in later).
GEMINI_STRONG_MODEL: str = os.getenv("GEMINI_STRONG_MODEL", "gemini-2.5-pro")

# --- Paths ---
DB_PATH: str = os.getenv("DB_PATH", "data/assistant.db")
