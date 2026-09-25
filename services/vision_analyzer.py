import json
import time
import traceback
from io import BytesIO
from collections.abc import Callable
from typing import Any, Literal

from google import genai
from google.genai import types
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from models.shelf_analysis import (
    CategoryPlacement,
    DetectedIssue,
    EmptyShelfPlan,
    EmptySpace,
    Recommendation,
    ShelfAnalysis,
    ShelfProduct,
    ShelfRow,
)
from utils.config import gemini_models_to_try, get_gemini_api_key, is_gemini_configured


class AnalysisError(Exception):
    def __init__(
        self,
        message: str,
        retryable: bool = False,
        retry_label: str = "Try Analysis Again",
        quota_exhausted: bool = False,
        model_unavailable: bool = False,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.retry_label = retry_label
        self.quota_exhausted = quota_exhausted
        self.model_unavailable = model_unavailable


AnalysisSource = Literal["gemini", "demo"]

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
DEMO_NOTICE = "Demo analysis — Gemini temporarily unavailable"


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


def _is_model_unavailable(exc: Exception) -> bool:
    code = _error_code(exc)
    message = _safe_exception_message(exc).upper()
    if code == 404:
        return True
    return any(
        marker in message
        for marker in (
            "NOT_FOUND",
            "NO LONGER AVAILABLE",
            "NOT AVAILABLE TO NEW USERS",
            "IS NOT FOUND",
        )
    )


def _is_transient_error(exc: Exception) -> bool:
    code = _error_code(exc)
    if _is_quota_error(exc) or _is_model_unavailable(exc):
        return False
    if code in {400, 401, 403}:
        return False
    if code in {408, 500, 502, 503, 504}:
        return True
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    if "TIMEOUT" in type(exc).__name__.upper():
        return True
    message = _safe_exception_message(exc).upper()
    return any(marker in message for marker in ("UNAVAILABLE", "DEADLINE_EXCEEDED", "TIMED OUT", "HIGH DEMAND"))


def _user_error_message(exc: Exception) -> str:
    code = _error_code(exc)
    if _is_quota_error(exc):
        return "AI analysis is temporarily unavailable because the Gemini quota is exhausted.\nYour shelf photo is saved. A clearly labeled demo analysis can still be used for the rest of the walkthrough."
    if code in {401, 403}:
        return "The AI configuration needs to be checked."
    if code == 400:
        return "The AI could not process this shelf request. Please try again with a clear shelf photo."
    if _is_model_unavailable(exc):
        return "The AI model is not available for this account. Your shelf photo is saved."
    if _is_transient_error(exc):
        return "Shelf analysis is temporarily unavailable because the AI service is busy.\nYour shelf photo is safe. Please try again in a few minutes."
    return "The AI could not complete this shelf analysis. Please try again."


def _analysis_schema() -> dict[str, Any]:
    if hasattr(ShelfAnalysis, "model_json_schema"):
        return ShelfAnalysis.model_json_schema()
    return ShelfAnalysis.schema()


def build_demo_analysis(selected_goal: str) -> ShelfAnalysis:
    goal = selected_goal or "Overall Shelf Review"
    issues = [
        DetectedIssue(
            issue="Some products look harder to see than others.",
            severity="High",
            evidence="Shoppers may miss items that are hidden or sitting too far back.",
            recommendation="Bring products forward so labels face the walking area.",
        ),
        DetectedIssue(
            issue="There is unused space on the shelf.",
            severity="Medium",
            evidence="Empty gaps make the shelf look unfinished and harder to shop.",
            recommendation="Move nearby products together to fill the visible gaps.",
        ),
        DetectedIssue(
            issue="Similar products are not clearly grouped.",
            severity="Medium",
            evidence="A mixed layout makes it harder to find the right item quickly.",
            recommendation="Keep similar products together in simple groups.",
        ),
    ]
    recommendations = [
        Recommendation(
            action="Pull products forward so more labels can be seen.",
            reason="This makes the shelf easier to scan while walking past.",
            priority="High",
        ),
        Recommendation(
            action="Fill visible empty spaces with nearby products.",
            reason="A fuller shelf looks neater and uses the space better.",
            priority="Medium",
        ),
        Recommendation(
            action="Group similar items next to each other.",
            reason="Clear groups help shoppers find products faster.",
            priority="Medium",
        ),
    ]
    if "Visibility" in goal:
        recommendations[0].priority = "High"
    elif "Empty" in goal:
        recommendations[1].priority = "High"
    elif "Organization" in goal:
        recommendations[2].priority = "High"
    elif "Promotional" in goal or "Promotion" in goal:
        recommendations.append(
            Recommendation(
                action="Place the promotion area closer to eye level.",
                reason="Eye-level space is easier for shoppers to notice.",
                priority="High",
            )
        )
    rows = [
        ShelfRow(
            row_number=1,
            vertical_zone="Top",
            products=[ShelfProduct(label="Product Group A", approximate_position="left", group="Group A")],
            empty_spaces=[EmptySpace(position="right", size="visible")],
        ),
        ShelfRow(
            row_number=2,
            vertical_zone="Eye Level",
            products=[
                ShelfProduct(label="Product Group B", approximate_position="center", group="Group B"),
                ShelfProduct(label="Product Group C", approximate_position="right", group="Group C"),
            ],
        ),
        ShelfRow(
            row_number=3,
            vertical_zone="Hand Level",
            products=[ShelfProduct(label="Product Group D", approximate_position="left", group="Group D")],
            empty_spaces=[EmptySpace(position="center", size="visible")],
        ),
        ShelfRow(
            row_number=4,
            vertical_zone="Lower Level",
            products=[ShelfProduct(label="Product Group E", approximate_position="center", group="Group E")],
        ),
    ]
    return ShelfAnalysis(
        overall_score=72,
        visibility_score=68,
        organization_score=70,
        space_utilization_score=64,
        presentation_score=74,
        detected_products=["Product Group A", "Product Group B", "Product Group C"],
        detected_issues=issues,
        recommendations=recommendations,
        priority_actions=recommendations[:2],
        summary=(
            "This is a demo analysis because Gemini is temporarily unavailable. "
            f"The selected goal was {goal}. "
            "The sample result shows common shelf problems so the rest of ShelfSight can still be demonstrated. "
            "It is not a real reading of this photo."
        ),
        shelf_rows=rows,
    )


def _generate_with_model(
    client: genai.Client,
    model: str,
    image_bytes: bytes,
    mime_type: str,
    selected_goal: str,
) -> ShelfAnalysis:
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ANALYSIS_PROMPT.format(selected_goal=selected_goal),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_analysis_schema(),
            temperature=0.2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    return _parse_analysis(_response_text(response))


def analyze_shelf(
    image_bytes: bytes,
    mime_type: str,
    selected_goal: str,
    status_callback: Callable[[str], None] | None = None,
    skip_gemini: bool = False,
) -> tuple[ShelfAnalysis, AnalysisSource]:
    if not image_bytes:
        raise AnalysisError("No shelf photo was provided.")
    if len(image_bytes) > 20 * 1024 * 1024:
        raise AnalysisError("That shelf photo is too large. Please upload an image smaller than 20 MB.")
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise AnalysisError("Please upload a clear shelf photo.") from exc

    if skip_gemini:
        print("Using labeled demo analysis because Gemini was marked unavailable for this session.")
        return build_demo_analysis(selected_goal), "demo"

    if not is_gemini_configured():
        print("Gemini is not configured. Returning labeled demo analysis.")
        return build_demo_analysis(selected_goal), "demo"

    try:
        client = genai.Client(
            api_key=get_gemini_api_key(),
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=1,
                    http_status_codes=[408, 500, 502, 503, 504],
                )
            ),
        )
    except Exception as exc:
        print(f"Gemini client initialization failed: {_safe_exception_message(exc)}")
        traceback.print_exc()
        raise AnalysisError(_user_error_message(exc), retryable=_is_transient_error(exc)) from exc

    models = gemini_models_to_try()
    last_error: Exception | None = None
    for model_index, model in enumerate(models):
        for attempt in range(MAX_RETRIES + 1):
            try:
                if status_callback is not None:
                    status_callback("Analyzing your shelf...")
                print(f"Gemini analysis using model {model} (attempt {attempt + 1})")
                analysis = _generate_with_model(client, model, image_bytes, mime_type, selected_goal)
                return analysis, "gemini"
            except AnalysisError:
                raise
            except Exception as exc:
                last_error = exc
                print(f"Gemini analysis failed for model {model}: {_safe_exception_message(exc)}")
                traceback.print_exc()
                if _is_quota_error(exc):
                    print("Gemini quota exhausted. Stopping further API retries and using labeled demo analysis.")
                    if status_callback is not None:
                        status_callback(DEMO_NOTICE)
                    return build_demo_analysis(selected_goal), "demo"
                if _is_model_unavailable(exc):
                    print(f"Model {model} is unavailable. Trying the next configured model if one exists.")
                    break
                if not _is_transient_error(exc) or attempt >= MAX_RETRIES:
                    if model_index < len(models) - 1 and _is_transient_error(exc):
                        break
                    raise AnalysisError(_user_error_message(exc), retryable=_is_transient_error(exc)) from exc
                if status_callback is not None:
                    status_callback("The AI service is temporarily busy. Retrying your shelf analysis...")
                time.sleep(RETRY_DELAYS_SECONDS[attempt])

    if last_error is not None and (_is_model_unavailable(last_error) or _is_quota_error(last_error)):
        print("No available Gemini model could complete analysis. Using labeled demo analysis.")
        if status_callback is not None:
            status_callback(DEMO_NOTICE)
        return build_demo_analysis(selected_goal), "demo"
    raise AnalysisError(
        "Shelf analysis is temporarily unavailable because the AI service is busy.\nYour shelf photo is safe. Please try again in a few minutes.",
        retryable=True,
    )


EMPTY_SHELF_PROMPT = """
You are ShelfSight, a helpful retail merchandising assistant for small shop owners.

Analyze the uploaded EMPTY shelf photograph. The shelf has approximately {shelf_levels} shelf levels.
The shopkeeper wants to stock these product categories: {categories_str}.

Determine the best placement for each selected product category across the shelf levels:
- Top level: Best for premium items, impulse boxes, chocolates, cookies.
- Eye level: Best for fast movers, popular biscuits, high-demand items.
- Hand/Middle level: Best for snacks, chips, everyday essentials.
- Lower/Bottom level: Best for heavy items, large drink bottles, bulk chips.

Return valid JSON conforming to the schema.
Write in simple, clear everyday English.
"""


def build_demo_empty_plan(shelf_levels: int, categories: list[str]) -> EmptyShelfPlan:
    zones_by_category = {
        "Chocolates": ("Top", "Chocolates at top level catch impulse attention and look attractive.", "Keep neat facing forward."),
        "Cookies": ("Top", "Cookies sell well on higher shelves near eye sight.", "Place premium packaging visible."),
        "Biscuits": ("Eye Level", "Biscuits are fast movers; placing them at eye level maximizes quick sales.", "Keep popular brands centered."),
        "Drinks": ("Bottom", "Cold or bottled drinks on the bottom shelf provide stable support for heavy bottles.", "Align bottles neatly."),
        "Snacks": ("Hand Level", "Snacks at hand level are quick and easy to pick up.", "Group similar snack packs together."),
        "Chips": ("Hand Level", "Chips at hand level are easy to reach for impulse shoppers.", "Stack upright so bags remain visible."),
        "Other": ("Lower Level", "General items belong neatly on lower shelf levels.", "Arrange by size from large to small."),
    }

    placements = []
    used_categories = set()
    available_zones = ["Top", "Eye Level", "Hand Level", "Lower Level", "Bottom"]
    if shelf_levels == 2:
        available_zones = ["Top", "Bottom"]
    elif shelf_levels == 3:
        available_zones = ["Top", "Eye Level", "Bottom"]
    elif shelf_levels == 4:
        available_zones = ["Top", "Eye Level", "Hand Level", "Bottom"]

    for idx, cat in enumerate(categories):
        if cat in used_categories:
            continue
        used_categories.add(cat)

        if cat in zones_by_category:
            zone, reason, tip = zones_by_category[cat]
            if zone not in available_zones:
                if zone == "Hand Level":
                    zone = "Eye Level" if "Eye Level" in available_zones else "Top"
                elif zone in {"Lower Level", "Bottom"}:
                    zone = available_zones[-1]
                else:
                    zone = available_zones[0]
        else:
            z_idx = min(idx, len(available_zones) - 1)
            zone = available_zones[z_idx]
            reason = f"Place {cat} neatly for good visibility."
            tip = "Keep labels facing forward."

        placements.append(CategoryPlacement(
            category=cat,
            recommended_zone=zone,  # type: ignore
            reason=reason,
            tip=tip,
        ))

    return EmptyShelfPlan(
        shelf_count=shelf_levels,
        summary=f"Recommended placement guide for stocking {len(categories)} product categories on your {shelf_levels}-level shelf.",
        placements=placements,
    )


def analyze_empty_shelf(
    image_bytes: bytes,
    mime_type: str,
    shelf_levels: int,
    categories: list[str],
    status_callback: Callable[[str], None] | None = None,
    skip_gemini: bool = False,
) -> tuple[EmptyShelfPlan, AnalysisSource]:
    if not image_bytes:
        raise AnalysisError("No empty shelf photo was provided.")

    if skip_gemini or not is_gemini_configured():
        return build_demo_empty_plan(shelf_levels, categories), "demo"

    try:
        client = genai.Client(
            api_key=get_gemini_api_key(),
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1, http_status_codes=[408, 500, 502, 503, 504])
            ),
        )
        schema = EmptyShelfPlan.model_json_schema() if hasattr(EmptyShelfPlan, "model_json_schema") else EmptyShelfPlan.schema()
        
        models = gemini_models_to_try()
        for model in models:
            try:
                if status_callback:
                    status_callback(f"Analyzing empty shelf layout with {model}...")
                response = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        EMPTY_SHELF_PROMPT.format(shelf_levels=shelf_levels, categories_str=", ".join(categories)),
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.2,
                    ),
                )
                text = _response_text(response)
                if text.startswith("```"):
                    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                payload = json.loads(text)
                plan = EmptyShelfPlan.model_validate(payload) if hasattr(EmptyShelfPlan, "model_validate") else EmptyShelfPlan.parse_obj(payload)
                return plan, "gemini"
            except Exception as exc:
                print(f"Empty shelf analysis model {model} failed: {_safe_exception_message(exc)}")
                continue

    except Exception as exc:
        print(f"Empty shelf analysis client failed: {_safe_exception_message(exc)}")

    return build_demo_empty_plan(shelf_levels, categories), "demo"

