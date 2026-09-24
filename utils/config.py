import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

configured_model = os.getenv("GEMINI_MODEL", "").strip()
GEMINI_MODEL = configured_model or "gemini-3.5-flash-lite"


def get_gemini_api_key() -> str:
	return os.getenv("GEMINI_API_KEY", "").strip()


def is_gemini_configured() -> bool:
	return bool(get_gemini_api_key())
