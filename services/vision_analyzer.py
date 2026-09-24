import json
import time
import traceback
from io import BytesIO
from collections.abc import Callable
from typing import Any

from google import genai
from google.genai import types
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from models.shelf_analysis import ShelfAnalysis
from utils.config import GEMINI_MODEL, get_gemini_api_key, is_gemini_configured


class AnalysisError(Exception):
    def __init__(self, message: str, retryable: bool = False, retry_label: str = "Try Analysis Again"):
        super().__init__(message)
        self.retryable = retryable
        self.retry_label = retry_label


ANALYSIS_PROMPT = """
You are ShelfSight, a friendly helper for a store manager or store employee. Use simple, clear, everyday English.

Analyze the uploaded supermarket shelf photograph. Base every observation ONLY on what is visibly present in the image. Do not invent products, prices, empty spaces, or problems that cannot reasonably be observed.

Evaluate:
1. Product visibility
2. Shelf organization
3. Product facing consistency
4. Empty or underutilized shelf space
5. Product grouping
6. Promotional visibility
7. Shelf balance
8. Possible misplaced products
9. Overall merchandising quality

The user selected this objective: {selected_goal}
Focus the recommendations particularly on this objective.

Return only valid JSON matching the supplied schema. Follow all of these writing rules:
- Write a summary of 2 to 4 short sentences. Say what looks good, then say what needs attention.
- Use short sentences and common words. Write for someone with basic English.
- Use visible facts only. Do not claim sales, inventory totals, customer behavior, revenue, or product performance.
- For every issue, make `issue` a short, clear problem. Make `evidence` say why it matters in simple words. Make `recommendation` one clear action.
- Use the words "products", "items", "shelf", "space", "walking area", and "looks clean" instead of specialist terms.
- Do not use words such as merchandise density, facings, planogram, gondola, overstock, protruding, merchandising deficiency, category blocks, or visual merchandising. Explain any unavoidable technical term immediately in simple English.
- Prefer "Similar products are grouped together" over "structured product category blocks" and "Most of the shelf space is being used" over "spatial utilization".
- Do not invent details. If something cannot be seen, say that it is not clear from the photo.
- Scores must reflect the photograph and may differ between images. Keep the score fields as numbers from 0 to 100.
- If shelf rows can be seen, return them in `shelf_rows`. Use approximate positions such as "left", "center", or "right"; never invent exact coordinates.
- For each row, use only the zones Top, Eye Level, Hand Level, Lower Level, or Unclear. Add products, visible empty spaces, and simple groups only when they can be seen.
- Use neutral labels such as "Product Group A" when a product name is not clear. Never invent brand names.
- Keep `shelf_rows` empty when the shelf structure cannot be seen reliably.
"""

MAX_RETRIES = 3
RETRY_DELAYS_SECONDS = (2, 5, 10)


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if not text:
        raise AnalysisError("The analysis service returned an empty response.")
    return text.strip()


def _parse_analysis(text: str) -> ShelfAnalysis:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        payload = json.loads(cleaned)
        if hasattr(ShelfAnalysis, "model_validate"):
            return ShelfAnalysis.model_validate(payload)
        return ShelfAnalysis.parse_obj(payload)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise AnalysisError("The analysis response was not valid shelf-analysis data.") from exc


def _safe_exception_message(exc: Exception) -> str:
    message = str(exc)
    api_key = get_gemini_api_key()
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    return message or "No additional error details were provided."


def _error_code(exc: Exception) -> int | None:
    code = getattr(exc, "code", None)
    return code if isinstance(code, int) else None


def _is_quota_error(exc: Exception) -> bool:
    code = _error_code(exc)
    if code == 429:
        return True
    message = _safe_exception_message(exc).upper()
    return any(marker in message for marker in ("RESOURCE_EXHAUSTED", "RATE LIMIT", "RATE_LIMIT", "QUOTA"))


def _is_transient_error(exc: Exception) -> bool:
    code = _error_code(exc)
    if _is_quota_error(exc):
        return False
    if code in {400, 401, 403, 404}:
        return False
    if code in {408, 500, 502, 503, 504}:
        return True
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    if "TIMEOUT" in type(exc).__name__.upper():
        return True
    message = _safe_exception_message(exc).upper()
    return any(
        marker in message
        for marker in ("UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED", "TIMED OUT")
    )


def _user_error_message(exc: Exception) -> str:
    code = _error_code(exc)
    if _is_quota_error(exc):
        return "AI analysis is temporarily unavailable.\nYour shelf photo is saved safely. Please try again later."
    if code in {401, 403}:
        return "The AI configuration needs to be checked."
    if code == 400:
        return "The AI could not process this shelf request. Please try again with a clear shelf photo."
    if code == 404:
        return "The AI configuration needs to be checked."
    if _is_transient_error(exc):
        return "Shelf analysis is temporarily unavailable because the AI service is busy.\nYour shelf photo is safe. Please try again in a few minutes."
    return "The AI could not complete this shelf analysis. Please try again."


def analyze_shelf(
    image_bytes: bytes,
    mime_type: str,
    selected_goal: str,
    status_callback: Callable[[str], None] | None = None,
) -> ShelfAnalysis:
    if not is_gemini_configured():
        raise AnalysisError("AI analysis is not configured yet.")
    if not image_bytes:
        raise AnalysisError("No shelf photo was provided.")
    if len(image_bytes) > 20 * 1024 * 1024:
        raise AnalysisError("That shelf photo is too large. Please upload an image smaller than 20 MB.")
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise AnalysisError("Please upload a clear shelf photo.") from exc

    try:
        client = genai.Client(api_key=get_gemini_api_key())
    except Exception as exc:
        print(f"Gemini client initialization failed: {_safe_exception_message(exc)}")
        traceback.print_exc()
        raise AnalysisError(_user_error_message(exc), retryable=_is_transient_error(exc)) from exc

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    ANALYSIS_PROMPT.format(selected_goal=selected_goal),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ShelfAnalysis.model_json_schema() if hasattr(ShelfAnalysis, "model_json_schema") else ShelfAnalysis.schema(),
                    temperature=0.2,
                ),
            )
            return _parse_analysis(_response_text(response))
        except AnalysisError:
            raise
        except Exception as exc:
            print(f"Gemini analysis attempt {attempt + 1} failed: {_safe_exception_message(exc)}")
            traceback.print_exc()
            if _is_quota_error(exc):
                raise AnalysisError(
                    _user_error_message(exc),
                    retryable=True,
                    retry_label="Try Again",
                ) from exc
            if not _is_transient_error(exc) or attempt >= MAX_RETRIES:
                raise AnalysisError(_user_error_message(exc), retryable=_is_transient_error(exc)) from exc
            if status_callback is not None:
                status_callback("Gemini is temporarily busy. Retrying your shelf analysis...")
            time.sleep(RETRY_DELAYS_SECONDS[attempt])

    raise AnalysisError("Shelf analysis is temporarily unavailable because the AI service is busy.\nYour shelf photo is safe. Please try again in a few minutes.", retryable=True)
