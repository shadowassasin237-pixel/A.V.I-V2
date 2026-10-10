"""
A.V.I. Configuration
Centralized settings. Override values via environment variables or a .env file.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv  # optional
    _ENV_PATH = Path(__file__).parent / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH)
except ImportError:
    pass


# ================================================================
# PATHS
# ================================================================

PROJECT_ROOT = Path(__file__).parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
MEMORY_FILE = DATA_DIR / "memory.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ================================================================
# VOICE
# ================================================================

LANGUAGE = os.getenv("AVI_LANGUAGE", "en-IN")
TTS_RATE = int(os.getenv("AVI_TTS_RATE", "175"))
TTS_VOLUME = float(os.getenv("AVI_TTS_VOLUME", "1.0"))

# Inworld TTS voice (LiveKit inference.TTS). Default is "Arjun".
# Other popular picks: Priya, Ashley, Mark, Sarah, Brian, Wendy, Deborah, Alex.
AVI_VOICE = os.getenv("AVI_VOICE", "Arjun").strip() or "Arjun"

# A friendly list shown in the GUI settings dialog. The actual TTS
# engine accepts any voice id Inworld/LiveKit exposes.
INWORLD_VOICES = [
    "Arjun",    # default — Indian English male
    "Priya",    # Indian English female
    "Ashley",   # American English female
    "Mark",     # American English male
    "Sarah",    # American English female
    "Brian",    # American English male
    "Wendy",    # American English female
    "Deborah",  # American English female
    "Alex",     # American English male
    "Emma",     # British English female
    "Hana",     # Japanese-accented English female
    "Ian",      # British English male
]



# ================================================================
# LIVEKIT / INWORLD VOICE
# ================================================================

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "").strip()
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "").strip()
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "").strip()
LIVEKIT_ROOM = os.getenv("LIVEKIT_ROOM", "avi-room").strip() or "avi-room"
LIVEKIT_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "avi").strip() or "avi"
VOICE_PROVIDER = "Inworld via LiveKit"
VOICE_NAME = "Arjun"
VOICE_MODEL = "inworld/inworld-tts-2"


# ================================================================
# DESKTOP / VISION / IMAGE TOOLS
# ================================================================

ALLOW_COMPUTER_CONTROL = os.getenv("AVI_ALLOW_COMPUTER_CONTROL", "0").strip().lower() in {"1", "true", "yes", "on"}
IMAGE_API_URL = os.getenv("AVI_IMAGE_API_URL", "").strip()
IMAGE_MODEL = os.getenv("AVI_IMAGE_MODEL", "gpt-image-1").strip()

# ================================================================
# WEB SEARCH
# ================================================================

WEB_MAX_RESULTS = int(os.getenv("AVI_WEB_MAX_RESULTS", "5"))


# ================================================================
# LLM (OpenRouter)
# ================================================================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv(
    "AVI_LLM_BASE_URL", "https://openrouter.ai/api/v1"
).rstrip("/")

# Any model id from https://openrouter.ai/models
# Must support tool calling, or web search / weather / news won't fire.
LLM_MODEL = os.getenv("AVI_LLM_MODEL", "openai/gpt-4o-mini")

# Quick-pick list shown in the GUI model dropdown. These cover the
# most common picks; the user can still type any custom id.
POPULAR_MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "openai/gpt-4-turbo",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-haiku",
    "google/gemini-2.0-flash-exp",
    "google/gemini-pro-1.5",
    "meta-llama/llama-3.1-70b-instruct",
    "meta-llama/llama-3.1-8b-instruct:free",
    "qwen/qwen-2.5-72b-instruct",
    "deepseek/deepseek-chat",
    "mistralai/mistral-nemo",
]

# Optional attribution headers shown on openrouter.ai rankings.
OPENROUTER_APP_NAME = os.getenv("AVI_APP_NAME", "A.V.I.")
OPENROUTER_SITE_URL = os.getenv("AVI_SITE_URL", "")


# ================================================================
# GUI
# ================================================================

GUI_TITLE = "A.V.I. - Artificial Voice Intelligence"
GUI_WIDTH = 1180
GUI_HEIGHT = 740
GUI_MIN_WIDTH = 900
GUI_MIN_HEIGHT = 620
