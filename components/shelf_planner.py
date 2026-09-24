import html
from io import BytesIO

import streamlit as st
from PIL import Image, ImageDraw

from models.shelf_analysis import ShelfAnalysis


SCENARIO_OPTIONS = [
    "Improve Product Visibility",
    "Reduce Empty Space",
    "Improve Organization",
    "Highlight Promotions",
    "Improve Shelf Presentation",
]


def score_values(analysis: ShelfAnalysis) -> dict[str, int]:
    return {
        "Shelf Health": analysis.overall_score,
        "Visibility": analysis.visibility_score,
        "Organization": analysis.organization_score,
        "Space Utilization": analysis.space_utilization_score,
        "Presentation": analysis.presentation_score,
    }


def scenario_scores(analysis: ShelfAnalysis, scenario: str) -> dict[str, int]:
    scores = score_values(analysis)
    focus = {
        "Improve Product Visibility": "Visibility",
        "Reduce Empty Space": "Space Utilization",
        "Improve Organization": "Organization",
        "Highlight Promotions": "Visibility",
        "Improve Shelf Presentation": "Presentation",
    }[scenario]
    scores[focus] = min(100, scores[focus] + 6)
    scores["Shelf Health"] = min(100, round(sum(scores.values()) / len(scores)))
    return scores


def scenario_explanation(scenario: str) -> str:
    return {
        "Improve Product Visibility": "We would place products so more of them are easy to see.",
        "Reduce Empty Space": "We would bring products closer together where the photo shows empty space.",
        "Improve Organization": "We would group similar products together so the shelf is easier to understand.",
        "Highlight Promotions": "We would place visible promotion areas closer to eye level when the shelf rows are known.",
        "Improve Shelf Presentation": "We would arrange visible products more neatly and make the display easier to read.",
    }[scenario]


def _fallback_label(index: int) -> str:
    return f"Product Group {chr(ord('A') + index)}"


def render_shelf_plan(analysis: ShelfAnalysis, title: str = "AI Recommended Layout", scenario: str | None = None) -> None:
    st.markdown(f"<div class='analysis-section'><h2>{html.escape(title)}</h2></div>", unsafe_allow_html=True)
    if not analysis.shelf_rows:
        st.info("Gemini could not reliably map the shelf rows in this photo. A visual shelf plan is not shown so we do not guess positions.")
        return

    st.caption("This plan uses only shelf rows and products Gemini could identify from the uploaded photo.")
    if scenario:
        st.caption(f"Scenario change: {scenario}")
    for row in analysis.shelf_rows:
        zone = html.escape(row.vertical_zone)
        product_markup = []
        for index, product in enumerate(row.products):
            label = product.label or _fallback_label(index)
            product_markup.append(
                f"<span class='status healthy' title='Approximate position: {html.escape(product.approximate_position)}'>"
                f"{html.escape(label)}<br><small>{html.escape(product.group)}</small></span>"
            )
        for empty_space in row.empty_spaces:
            product_markup.append(
                f"<span class='status review'>Empty space<br><small>{html.escape(empty_space.position)}</small></span>"
            )
        if not product_markup:
            product_markup.append("<span class='status review'>No clear products or empty spaces found</span>")
        st.markdown(
            f"<div class='panel' style='margin:.7rem 0'><strong>Row {row.row_number} / {zone}</strong>"
            f"<div style='display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.75rem'>{''.join(product_markup)}</div></div>",
            unsafe_allow_html=True,
        )


def render_zone_guide(analysis: ShelfAnalysis) -> None:
    st.markdown("<div class='analysis-section'><h2>Shelf Zones</h2></div>", unsafe_allow_html=True)
    descriptions = {
        "Top": "Items at the top are usually harder to notice.",
        "Eye Level": "Products here are easier to notice.",
        "Hand Level": "Products here are easy to reach.",
        "Lower Level": "Items here may be harder to notice and reach.",
        "Unclear": "The shelf zone is not clear from this photo.",
    }
    zones = {row.vertical_zone for row in analysis.shelf_rows}
    columns = st.columns(4, gap="small")
    for column, zone in zip(columns, ["Top", "Eye Level", "Hand Level", "Lower Level"]):
        with column:
            status = descriptions[zone] if zone in zones else "This zone was not clear in the photo."
            st.markdown(f"**{zone.upper()}**  \n{status}")


def render_current_vs_recommended(image: bytes, analysis: ShelfAnalysis) -> None:
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**CURRENT**")
        st.image(image, use_container_width=True)
    with right:
        st.markdown("**RECOMMENDED**")
        render_shelf_plan(analysis, "Recommended shelf layout")


def render_shelf_heatmap(image: bytes, analysis: ShelfAnalysis) -> None:
    st.markdown("<div class='analysis-section'><h2>Shelf Problem Map</h2></div>", unsafe_allow_html=True)
    if not analysis.shelf_rows:
        st.info("A heatmap is not shown because Gemini could not reliably map the shelf rows in this photo.")
        return
    with Image.open(BytesIO(image)).convert("RGBA") as source:
        overlay = Image.new("RGBA", source.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        row_height = max(1, source.height // len(analysis.shelf_rows))
        for index, row in enumerate(analysis.shelf_rows):
            y0 = index * row_height
            y1 = source.height if index == len(analysis.shelf_rows) - 1 else (index + 1) * row_height
            color = (46, 125, 50, 80) if row.products and not row.empty_spaces else (245, 166, 35, 95)
            label = "Good area" if row.products and not row.empty_spaces else "Needs attention"
            if row.empty_spaces:
                color = (198, 40, 40, 105)
                label = "Empty space"
            draw.rectangle((0, y0, source.width, y1), fill=color, outline=(255, 255, 255, 180), width=3)
            draw.text((12, y0 + 10), f"{label} / {row.vertical_zone}", fill=(255, 255, 255, 255))
        st.image(Image.alpha_composite(source, overlay).convert("RGB"), use_container_width=True)
    st.caption("GREEN = Good   YELLOW = Needs attention   RED = Needs improvement")


def render_scenario_comparison(image: bytes, analysis: ShelfAnalysis, scenario: str) -> None:
    current = score_values(analysis)
    projected = scenario_scores(analysis, scenario)
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**CURRENT**")
        st.image(image, use_container_width=True)
        st.markdown(f"**Current Shelf Health:** {current['Shelf Health']} / 100")
    with right:
        st.markdown("**WHAT-IF**")
        render_shelf_plan(analysis, "Scenario layout", scenario)
        st.markdown(f"**Scenario Shelf Health:** {projected['Shelf Health']} / 100")
    st.caption("Model-based scenario estimate. This is not a new shelf measurement and does not guarantee sales improvement.")
    metric_columns = st.columns(len(current), gap="small")
    for column, label in zip(metric_columns, current):
        with column:
            change = projected[label] - current[label]
            st.metric(label, f"{projected[label]} / 100", f"{change:+d}")
    st.markdown("<div class='analysis-section'><h2>Why this arrangement?</h2></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='analysis-summary'>{html.escape(scenario_explanation(scenario))}</div>", unsafe_allow_html=True)
