import html
from io import BytesIO

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

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
        "Improve Product Visibility": "Place products so more of them are easy to see.",
        "Reduce Empty Space": "Bring products closer together where the photo shows empty space.",
        "Improve Organization": "Group similar products together so the shelf is easier to understand.",
        "Highlight Promotions": "Keep promotion areas in visible shelf positions when the shelf rows are known.",
        "Improve Shelf Presentation": "Arrange visible products more neatly and make the display easier to read.",
    }[scenario]


def _fallback_label(index: int) -> str:
    return f"Product Group {chr(ord('A') + index)}"


def _load_font(size: int):
    """Use a common Windows font when available; fall back safely."""
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _issue_texts(analysis: ShelfAnalysis) -> list[str]:
    """Collect the AI-detected issue text safely."""
    return [
        " ".join(
            str(value)
            for value in (getattr(issue, "issue", ""), getattr(issue, "evidence", ""), getattr(issue, "recommendation", ""))
            if value
        ).lower()
        for issue in getattr(analysis, "detected_issues", [])
    ]


def _row_guidance(row, analysis: ShelfAnalysis) -> tuple[str, tuple[int, int, int, int], str]:
    """Match visual guidance to the actual issues Gemini reported.

    Empty shelf space remains a red action. Other colors are driven by the
    detected issue text, so a lower-basket problem cannot accidentally appear
    green just because products are present there.
    """
    texts = _issue_texts(analysis)
    zone = str(getattr(row, "vertical_zone", "")).lower()

    # Empty space is a direct visual action and should remain strongest.
    if getattr(row, "empty_spaces", None):
        return "FILL THIS SPACE", (220, 38, 38, 150), "CHANGE / FILL"

    # Match the specific problems shown in the analysis cards.
    stacking_issue = any(
        any(word in text for word in ("vertical stacking", "stacked very high", "tall stack", "stacked high"))
        for text in texts
    )
    basket_issue = any(
        any(word in text for word in ("lower basket", "floor basket", "mixed items", "mixed item", "loose and mixed"))
        for text in texts
    )

    if stacking_issue and zone in {"top", "eye level"}:
        return "LOWER TALL STACKS", (245, 166, 35, 150), "CHECK / REVIEW"

    if basket_issue and zone in {"lower level", "unclear"}:
        return "SORT MIXED ITEMS", (245, 166, 35, 150), "CHECK / REVIEW"

    # If Gemini reports a general organization problem, do not call the row
    # perfect; mark it for review instead of showing a misleading green area.
    organization_issue = any(
        any(word in text for word in ("not clearly grouped", "mixed", "disorganized", "organization", "misplaced"))
        for text in texts
    )
    if organization_issue and zone in {"lower level", "unclear"}:
        return "CHECK THIS AREA", (245, 166, 35, 150), "CHECK / REVIEW"

    if getattr(row, "products", None):
        return "NO ISSUE DETECTED", (35, 140, 65, 85), "KEEP / GOOD"

    return "CHECK THIS AREA", (245, 166, 35, 145), "CHECK / REVIEW"


def _create_recommended_image(image: bytes, analysis: ShelfAnalysis) -> Image.Image | None:
    """
    Create a visual recommendation from the real uploaded shelf photo.

    This does not invent or redraw products. It keeps the actual photo and
    overlays the AI-detected shelf rows with clear green/yellow/red guidance,
    arrows and simple instructions.
    """
    if not analysis.shelf_rows:
        return None

    try:
        source = Image.open(BytesIO(image)).convert("RGB")
    except Exception:
        return None

    canvas = source.copy().convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    width, height = canvas.size
    row_height = max(1, height // len(analysis.shelf_rows))

    title_font = _load_font(max(20, width // 42))
    label_font = _load_font(max(16, width // 65))
    small_font = _load_font(max(13, width // 85))

    # Header makes it unmistakable that this is a recommendation, not a new photo.
    header_h = max(58, height // 10)
    draw.rectangle((0, 0, width, header_h), fill=(18, 30, 27, 225))
    draw.text(
        (18, 12),
        "RECOMMENDED SHELF",
        font=title_font,
        fill=(255, 255, 255, 255),
    )
    draw.text(
        (18, header_h - 25),
        "Visual guide based on the shelf analysis",
        font=small_font,
        fill=(235, 245, 238, 255),
    )

    # Strong row overlays. These are intentionally translucent so the real
    # products remain visible underneath.
    for index, row in enumerate(analysis.shelf_rows):
        y0 = header_h + index * max(1, (height - header_h) // len(analysis.shelf_rows))
        y1 = (
            height
            if index == len(analysis.shelf_rows) - 1
            else header_h + (index + 1) * max(1, (height - header_h) // len(analysis.shelf_rows))
        )

        message, color, guidance = _row_guidance(row, analysis)
        draw.rectangle((0, y0, width, y1), fill=color)

        # White guide line around each analyzed row.
        draw.line((0, y0, width, y0), fill=(255, 255, 255, 220), width=3)

        # Worker-friendly label.
        label_box_y = min(y0 + 12, max(12, y1 - 52))
        text_bbox = draw.textbbox((0, 0), message, font=label_font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        box_x1 = min(width - 12, 18 + text_w + 26)
        box_y1 = label_box_y + text_h + 18
        draw.rounded_rectangle(
            (12, label_box_y, box_x1, box_y1),
            radius=8,
            fill=(20, 20, 20, 210),
        )
        draw.text(
            (24, label_box_y + 7),
            message,
            font=label_font,
            fill=(255, 255, 255, 255),
        )

        # Add a simple arrow for rows needing action.
        if row.empty_spaces:
            arrow_y = (y0 + y1) // 2
            arrow_start = max(20, width - 210)
            arrow_end = max(80, width - 55)
            draw.line(
                (arrow_start, arrow_y, arrow_end, arrow_y),
                fill=(255, 255, 255, 255),
                width=7,
            )
            draw.polygon(
                [
                    (arrow_end, arrow_y),
                    (arrow_end - 24, arrow_y - 16),
                    (arrow_end - 24, arrow_y + 16),
                ],
                fill=(255, 255, 255, 255),
            )
            draw.text(
                (max(20, width - 360), arrow_y - 43),
                "PUT PRODUCTS HERE",
                font=small_font,
                fill=(255, 255, 255, 255),
            )
        elif guidance == "KEEP / GOOD":
            # A subtle green marker helps workers understand that this area
            # can stay as it is.
            marker_x = width - 58
            marker_y = max(y0 + 20, (y0 + y1) // 2 - 18)
            draw.ellipse(
                (marker_x, marker_y, marker_x + 34, marker_y + 34),
                fill=(30, 150, 70, 230),
                outline=(255, 255, 255, 255),
                width=3,
            )
            draw.text(
                (marker_x + 9, marker_y + 2),
                "✓",
                font=small_font,
                fill=(255, 255, 255, 255),
            )

    # Legend at the bottom.
    legend_y = max(8, height - 42)
    draw.rectangle((0, legend_y, width, height), fill=(18, 30, 27, 220))
    legend = [
        ("GREEN", (35, 140, 65, 255), "No issue detected"),
        ("YELLOW", (245, 166, 35, 255), "Check / review"),
        ("RED", (220, 38, 38, 255), "Change / fill"),
    ]
    x = 18
    for name, color, meaning in legend:
        draw.rounded_rectangle((x, legend_y + 9, x + 18, legend_y + 27), radius=4, fill=color)
        draw.text((x + 26, legend_y + 8), f"{name} = {meaning}", font=small_font, fill=(255, 255, 255, 255))
        x += max(150, width // 4)

    return Image.alpha_composite(canvas, overlay).convert("RGB")


def render_shelf_plan(
    analysis: ShelfAnalysis,
    title: str = "AI Recommended Layout",
    scenario: str | None = None,
) -> None:
    st.markdown(
        f"<div class='analysis-section'><h2>{html.escape(title)}</h2></div>",
        unsafe_allow_html=True,
    )
    if not analysis.shelf_rows:
        st.info(
            "Gemini could not reliably map the shelf rows in this photo. "
            "A visual shelf plan is not shown so we do not guess positions."
        )
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
                f"<span class='status healthy' title='Approximate position: "
                f"{html.escape(product.approximate_position)}'>"
                f"{html.escape(label)}<br><small>{html.escape(product.group)}</small></span>"
            )

        for empty_space in row.empty_spaces:
            product_markup.append(
                f"<span class='status priority'>Empty space<br>"
                f"<small>{html.escape(empty_space.position)}</small></span>"
            )

        if not product_markup:
            product_markup.append(
                "<span class='status review'>No clear products or empty spaces found</span>"
            )

        st.markdown(
            f"<div class='panel' style='margin:.7rem 0'>"
            f"<strong>Row {row.row_number} / {zone}</strong>"
            f"<div style='display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.75rem'>"
            f"{''.join(product_markup)}</div></div>",
            unsafe_allow_html=True,
        )


def render_zone_guide(analysis: ShelfAnalysis) -> None:
    st.markdown(
        "<div class='analysis-section'><h2>Shelf Zones</h2></div>",
        unsafe_allow_html=True,
    )
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
    """
    Main visual before/after experience.

    LEFT  = the real uploaded photo.
    RIGHT = the same real photo with AI-analysis-based recommended actions
            drawn on top. This avoids pretending that products were actually
            rearranged when no image-generation model has produced a new photo.
    """
    st.markdown(
        "<div class='analysis-section'><h2>Before and Recommended</h2>"
        "<p>The right side shows exactly where ShelfSight suggests you take action.</p></div>",
        unsafe_allow_html=True,
    )

    recommended = _create_recommended_image(image, analysis)

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown(
            "<div class='eyebrow'>BEFORE / YOUR PHOTO</div>",
            unsafe_allow_html=True,
        )
        st.image(image, use_container_width=True)

    with right:
        st.markdown(
            "<div class='eyebrow'>AFTER / RECOMMENDED VIEW</div>",
            unsafe_allow_html=True,
        )
        if recommended is not None:
            st.image(
                recommended,
                caption="AI-guided recommended view — use the arrows and colors as your shelf instructions.",
                use_container_width=True,
            )
        else:
            st.info("A recommended visual could not be created because shelf rows were not mapped reliably.")

    st.markdown(
        """
        <div style="display:flex;gap:1rem;flex-wrap:wrap;margin:.7rem 0 1rem">
            <span class="status healthy">🟢 NO ISSUE DETECTED</span>
            <span class="status review">🟡 CHECK / REVIEW</span>
            <span class="status priority">🔴 CHANGE / FILL</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_shelf_heatmap(image: bytes, analysis: ShelfAnalysis) -> None:
    st.markdown(
        "<div class='analysis-section'><h2>Where should you look?</h2></div>",
        unsafe_allow_html=True,
    )
    if not analysis.shelf_rows:
        st.info(
            "A problem map is not shown because Gemini could not reliably map "
            "the shelf rows in this photo."
        )
        return

    try:
        source = Image.open(BytesIO(image)).convert("RGBA")
    except Exception:
        st.info("The uploaded shelf image could not be opened for the visual map.")
        return

    overlay = Image.new("RGBA", source.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    row_height = max(1, source.height // len(analysis.shelf_rows))

    label_font = _load_font(max(16, source.width // 70))

    for index, row in enumerate(analysis.shelf_rows):
        y0 = index * row_height
        y1 = source.height if index == len(analysis.shelf_rows) - 1 else (index + 1) * row_height

        message, color, guidance = _row_guidance(row, analysis)

        draw.rectangle(
            (0, y0, source.width, y1),
            fill=color,
            outline=(255, 255, 255, 230),
            width=4,
        )

        # Dark label background makes the colors readable on bright shelves.
        text_bbox = draw.textbbox((0, 0), message, font=label_font)
        text_w = text_bbox[2] - text_bbox[0]
        box_x1 = min(source.width - 10, 20 + text_w + 28)
        draw.rounded_rectangle(
            (10, y0 + 10, box_x1, y0 + 52),
            radius=7,
            fill=(20, 20, 20, 205),
        )
        draw.text(
            (20, y0 + 17),
            message,
            font=label_font,
            fill=(255, 255, 255, 255),
        )

    st.image(
        Image.alpha_composite(source, overlay).convert("RGB"),
        use_container_width=True,
    )
    st.caption("🟢 NO ISSUE DETECTED  •  🟡 CHECK / REVIEW  •  🔴 CHANGE / FILL")


def render_scenario_comparison(
    image: bytes,
    analysis: ShelfAnalysis,
    scenario: str,
) -> None:
    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("**CURRENT / YOUR PHOTO**")
        st.image(image, use_container_width=True)

    with right:
        st.markdown("**WHAT-IF / RECOMMENDED VIEW**")
        recommended = _create_recommended_image(image, analysis)
        if recommended is not None:
            st.image(
                recommended,
                caption=f"Visual guide for: {scenario}",
                use_container_width=True,
            )
        else:
            render_shelf_plan(analysis, "Scenario layout", scenario)

    st.caption(
        "This is a visual planning guide based on the shelf analysis. "
        "It does not claim that products have physically moved."
    )

    st.markdown(
        "<div class='analysis-section'><h2>Why this change?</h2></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='analysis-summary'>{html.escape(scenario_explanation(scenario))}</div>",
        unsafe_allow_html=True,
    )
