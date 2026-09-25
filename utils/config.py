import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Proven with google-genai 2.24.0: image input + structured JSON.
# gemini-2.5-flash is listed for some keys but returns 404 for new users.
DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest"
configured_model = os.getenv("GEMINI_MODEL", "").strip()
GEMINI_MODEL = configured_model or DEFAULT_GEMINI_MODEL

GEMINI_MODEL_FALLBACKS = (
	"gemini-flash-lite-latest",
	"gemini-3.5-flash-lite",
	"gemini-3.5-flash",
	"gemini-flash-latest",
)


def get_gemini_api_key() -> str:
	return os.getenv("GEMINI_API_KEY", "").strip()


def is_gemini_configured() -> bool:
	return bool(get_gemini_api_key())


def gemini_models_to_try() -> list[str]:
	models: list[str] = []
	for model in (GEMINI_MODEL, *GEMINI_MODEL_FALLBACKS):
		if model and model not in models:
			models.append(model)
	return models
