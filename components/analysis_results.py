import html

import streamlit as st

from models.shelf_analysis import DetectedIssue, Recommendation, ShelfAnalysis


SEVERITY_CLASS = {"High": "analysis-high", "Medium": "analysis-medium", "Low": "analysis-low"}


def _score_explanation(label: str, score: int) -> str:
    if label == "Shelf Health":
        return "Your shelf looks good overall, with a few areas that may need improvement." if score < 90 else "Your shelf looks good overall."
    if label == "Product Visibility":
        return "Some products may be harder to see." if score < 90 else "Most products are easy to see."
    if label == "Organization":
        return "Products may need to be arranged more neatly." if score < 90 else "Products are mostly arranged neatly."
    if label == "Space Utilization":
        return "Some shelf space is not being used." if score < 90 else "Most of the available shelf space is being used."
    return "A few things may make the shelf look less neat." if score < 90 else "The shelf looks clean and attractive."


def _priority_explanation(priority: str) -> str:
    return {
        "High": "Needs attention soon.",
        "Medium": "Should be improved.",
        "Low": "Small improvement that can be made later.",
    }.get(priority, "")


def _render_issue(issue: DetectedIssue) -> None:
    severity_class = SEVERITY_CLASS.get(issue.severity, "analysis-low")
    priority_explanation = _priority_explanation(issue.severity)
    st.markdown(
        f"""
        <div class="analysis-item">
            <span class="analysis-badge {severity_class}">{html.escape(issue.severity)} priority</span><span>{html.escape(priority_explanation)}</span>
            <h3>{html.escape(issue.issue)}</h3>
            <p><strong>Why it matters:</strong> {html.escape(issue.evidence)}</p>
            <p><strong>What to do:</strong> {html.escape(issue.recommendation)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_recommendation(recommendation: Recommendation) -> None:
    priority_class = SEVERITY_CLASS.get(recommendation.priority, "analysis-low")
    priority_explanation = _priority_explanation(recommendation.priority)
    st.markdown(
        f"""
        <div class="analysis-action">
            <span class="analysis-badge {priority_class}">{html.escape(recommendation.priority)} priority</span><span>{html.escape(priority_explanation)}</span>
            <strong>{html.escape(recommendation.action)}</strong>
            <p>{html.escape(recommendation.reason)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_analysis_results(analysis: ShelfAnalysis) -> None:
    st.markdown('<div class="analysis-heading"><div class="eyebrow">AI SHELF ANALYSIS</div><h2>AI Shelf Analysis</h2></div>', unsafe_allow_html=True)
    metric_values = [
        ("Shelf Health", analysis.overall_score),
        ("Product Visibility", analysis.visibility_score),
        ("Organization", analysis.organization_score),
        ("Space Utilization", analysis.space_utilization_score),
        ("Presentation", analysis.presentation_score),
    ]
    metric_columns = st.columns(len(metric_values), gap="small")
    for column, (label, value) in zip(metric_columns, metric_values):
        with column:
            explanation = _score_explanation(label, value)
            st.markdown(f'<div class="analysis-metric"><span>{html.escape(label)}</span><strong>{value} / 100</strong><small>{html.escape(explanation)}</small></div>', unsafe_allow_html=True)

    st.markdown('<div class="analysis-section"><h2>What We Found</h2></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="analysis-summary">{html.escape(analysis.summary)}</div>', unsafe_allow_html=True)

    st.markdown('<div class="analysis-section"><h2>Detected Issues</h2></div>', unsafe_allow_html=True)
    if analysis.detected_issues:
        for issue in sorted(analysis.detected_issues, key=lambda item: {"High": 0, "Medium": 1, "Low": 2}[item.severity]):
            _render_issue(issue)
    else:
        st.info("No visible merchandising issues were identified in this photo.")

    recommendations = analysis.priority_actions or analysis.recommendations
    st.markdown('<div class="analysis-section"><h2>Recommended Actions</h2></div>', unsafe_allow_html=True)
    if recommendations:
        for recommendation in sorted(recommendations, key=lambda item: {"High": 0, "Medium": 1, "Low": 2}[item.priority]):
            _render_recommendation(recommendation)
    else:
        st.info("No recommendations were returned for this shelf photo.")
