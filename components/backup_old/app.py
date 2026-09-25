import html
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components

from components.analysis_results import render_analysis_results
from components.shelf_planner import (
    SCENARIO_OPTIONS,
    render_current_vs_recommended,
    render_scenario_comparison,
    render_shelf_plan,
    render_shelf_heatmap,
    render_zone_guide,
    scenario_scores,
    score_values,
)
from models.shelf_analysis import ShelfAnalysis
from services.vision_analyzer import AnalysisError, analyze_shelf


st.set_page_config(
    page_title="ShelfSight | Retail Merchandising Intelligence",
    page_icon="SS",
    layout="wide",
    initial_sidebar_state="expanded",
)


SECTIONS = [
    {"name": "Beverages", "score": 91, "status": "Healthy", "issues": 1, "tone": "healthy", "accent": "Citrus + cold drinks"},
    {"name": "Snacks", "score": 76, "status": "Review", "issues": 4, "tone": "review", "accent": "Impulse zone"},
    {"name": "Grocery", "score": 84, "status": "Healthy", "issues": 2, "tone": "healthy", "accent": "Everyday essentials"},
    {"name": "Personal Care", "score": 61, "status": "Priority", "issues": 7, "tone": "priority", "accent": "Needs a reset"},
    {"name": "Premium Display", "score": 88, "status": "Healthy", "issues": 1, "tone": "healthy", "accent": "Seasonal feature"},
]

NAV_GROUPS = {
    "MAIN": [("⌂", "Home"), ("▦", "My Store")],
    "MERCHANDISING": [("▤", "Inspect a Shelf"), ("✦", "Improve My Shelf"), ("↗", "Try a Scenario")],
    "TRACK": [("◷", "Store Progress"), ("!", "Challenges")],
    "ASSIST": [("✧", "ShelfSight Copilot"), ("▥", "Reports")],
}

UI_TEXT = {
    "English": {
        "language": "Language", "your_shelf": "Your Shelf",
        "what_found": "What did we find?", "what_change": "What should you change?",
        "before_after": "Before and After", "why": "Why this change?",
        "fixed": "I fixed it", "take_photo": "Take another photo",
        "current": "Current Shelf", "recommended": "Recommended Layout", "step": "Step",
    },
    "తెలుగు": {
        "language": "భాష", "your_shelf": "మీ షెల్ఫ్",
        "what_found": "ఏమి గుర్తించాము?", "what_change": "మీరు ఏమి మార్చాలి?",
        "before_after": "ముందు మరియు తరువాత", "why": "ఈ మార్పు ఎందుకు?",
        "fixed": "నేను మార్చాను", "take_photo": "మరొక ఫోటో తీయండి",
        "current": "ప్రస్తుత షెల్ఫ్", "recommended": "సిఫార్సు చేసిన అమరిక", "step": "దశ",
    },
    "हिन्दी": {
        "language": "भाषा", "your_shelf": "आपकी शेल्फ",
        "what_found": "हमने क्या पाया?", "what_change": "आपको क्या बदलना चाहिए?",
        "before_after": "पहले और बाद में", "why": "यह बदलाव क्यों?",
        "fixed": "मैंने ठीक कर दिया", "take_photo": "एक और फोटो लें",
        "current": "वर्तमान शेल्फ", "recommended": "सुझाया गया लेआउट", "step": "चरण",
    },
}

PAGE_BY_LABEL = {
    "Home": "Home",
    "My Store": "My Store",
    "Inspect a Shelf": "Inspect Shelf",
    "Improve My Shelf": "Improve Shelf",
    "Try a Scenario": "Try Scenario",
    "Store Progress": "Store Evolution",
    "Challenges": "Challenges",
    "ShelfSight Copilot": "ShelfSight Copilot",
    "Reports": "Reports",
}

IMAGE_DIR = Path(__file__).parent / "assets" / "images"
RETAIL_IMAGES = {
    "hero": ("retail_hero.jpg", "https://images.unsplash.com/photo-1534723452862-4c874018d66d?auto=format&fit=crop&w=1800&q=85"),
    "login": ("retail_login.jpg", "https://images.unsplash.com/photo-1579113800032-c38bd7635818?auto=format&fit=crop&w=1800&q=85"),
    "store": ("retail_store.jpg", "https://images.unsplash.com/photo-1601598851547-4302969d2a58?auto=format&fit=crop&w=1800&q=85"),
    "shelf": ("retail_shelf.jpg", "https://images.unsplash.com/photo-1583258292688-d0213dc5a3a8?auto=format&fit=crop&w=1800&q=85"),
    "beverages": ("retail_beverages.jpg", "https://images.unsplash.com/photo-1544145945-f90425340c7e?auto=format&fit=crop&w=900&q=80"),
    "snacks": ("retail_snacks.jpg", "https://images.unsplash.com/photo-1621939514649-280e2aa04a26?auto=format&fit=crop&w=900&q=80"),
    "grocery": ("retail_grocery.jpg", "https://images.unsplash.com/photo-1604719312566-8912e9227c6a?auto=format&fit=crop&w=900&q=80"),
    "personal_care": ("retail_personal_care.jpg", "https://images.unsplash.com/photo-1556228578-8c89e6adf883?auto=format&fit=crop&w=900&q=80"),
    "premium_display": ("retail_premium_display.jpg", "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?auto=format&fit=crop&w=900&q=80"),
}


def image_source(key: str) -> str:
    filename, fallback = RETAIL_IMAGES[key]
    local_path = IMAGE_DIR / filename
    return str(local_path) if local_path.exists() else fallback


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
        :root { --ink:#26241f; --secondary:#59564f; --paper:#f6f2e9; --panel:#fffdf8; --line:#ddd6c9; --orange:#d95f27; --orange-dark:#963f19; --green:#3f6749; --amber:#8d651b; --red:#963f31; }
        html, body, [class*="css"] { font-family:'DM Sans',sans-serif; color:var(--ink); }
        .stApp { background:var(--paper); }
        [data-testid="stHeader"] { background:rgba(246,242,233,.96); }
        [data-testid="stSidebar"] { background:#2d2c27; border-right:0; }
        [data-testid="stSidebar"] * { color:#f4efe5; }
        [data-testid="stSidebar"] .stButton button { border:0; background:transparent; color:#c1beb5; text-align:left; padding:.58rem .7rem; }
        [data-testid="stSidebar"] .stButton button:hover { color:#fffaf1; background:#45433b; }
        [data-testid="stSidebar"] .stButton button[kind="primary"] { color:#fffaf1; background:#b84e20; }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:#a9a69c; }
        .block-container { max-width:1440px; padding:clamp(1.5rem,4vw,3rem) clamp(1rem,4vw,4rem) 4rem; }
        h1, h2, h3 { color:var(--ink) !important; font-family:'Space Grotesk',sans-serif; letter-spacing:0; }
        h1 { font-size:clamp(2.8rem,6vw,5.8rem); line-height:.98; margin:.4rem 0 1.2rem; }
        h2 { font-size:2rem; } p, [data-testid="stMarkdownContainer"] p { color:var(--secondary); }
        .stButton button, .stDownloadButton button { border-radius:7px; font-weight:700; border:1px solid #cfc7b9; min-height:2.6rem; }
        .stButton button[kind="primary"] { background:var(--orange); color:#fffdf8; border-color:var(--orange); }
        .stTextInput input, .stSelectbox [data-baseweb="select"], .stFileUploader section { background:var(--panel); border-color:#cfc7b9; color:var(--ink); }
        .brand-lockup { padding:.5rem .25rem 1.7rem; }
        .brand-mark { display:inline-flex; width:34px; height:34px; align-items:center; justify-content:center; background:#e66f32; color:#fff8ef; font:700 13px 'Space Grotesk'; margin-right:.55rem; border-radius:8px 8px 2px 8px; }
        .brand-name { font:700 18px 'Space Grotesk'; letter-spacing:-.5px; }
        .brand-sub { color:#a9a69c; font-size:10px; letter-spacing:1.2px; text-transform:uppercase; margin-top:9px; }
        .nav-group { color:#a9a69c; font-size:10px; font-weight:700; letter-spacing:1.5px; margin:1.15rem .5rem .3rem; }
        .eyebrow { color:var(--orange-dark); font-size:.72rem; font-weight:700; letter-spacing:1.8px; text-transform:uppercase; }
        .hero-copy { padding:clamp(2rem,7vh,4.5rem) 0 2.5rem; } .hero-copy h1 { color:#171717 !important; font-size:56px; line-height:1.03; max-width:650px; margin:.55rem 0 1.25rem; } .hero-copy p { font-size:1.08rem; line-height:1.7; max-width:560px; }
        .hero-note { display:flex; gap:.75rem; align-items:center; margin-top:2.2rem; color:var(--secondary); font-size:.82rem; }
        .hero-note span { width:8px; height:8px; background:var(--green); border-radius:50%; display:inline-block; }
        .section-heading { display:flex; align-items:end; justify-content:space-between; margin:3.6rem 0 1.2rem; } .section-heading h2 { margin:.25rem 0 0; }
        .panel { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:1.25rem; box-shadow:0 8px 22px rgba(70,58,40,.05); }
        .metric-panel { min-height:126px; border-top:4px solid var(--orange); position:relative; overflow:hidden; }
        .metric-panel:after { content:''; height:3px; position:absolute; bottom:20px; left:20px; right:20px; background:repeating-linear-gradient(90deg,var(--line) 0 15px,transparent 15px 20px); }
        .metric-label { text-transform:uppercase; letter-spacing:1px; font-size:.67rem; color:var(--secondary); font-weight:700; }
        .metric-value { color:var(--ink); font:700 2.1rem 'Space Grotesk'; margin-top:.4rem; } .metric-detail { font-size:.73rem; color:var(--green); margin-top:.2rem; }
        .health-ring { width:160px; height:160px; border-radius:50%; display:grid; place-items:center; background:conic-gradient(var(--orange) 84%,#e6dfd4 0); position:relative; }
        .health-ring:after { content:''; position:absolute; inset:13px; border-radius:50%; background:var(--panel); }
        .health-score { color:var(--ink); position:relative; z-index:1; text-align:center; font:700 2.7rem 'Space Grotesk'; } .health-score small { display:block; color:var(--secondary); font:600 .64rem 'DM Sans'; letter-spacing:1.2px; text-transform:uppercase; }
        .layout-card { background:#eee9df; border:1px solid #d5ccbd; border-radius:12px; padding:1.4rem; min-height:232px; position:relative; overflow:hidden; }
        .layout-card:before { content:''; position:absolute; inset:0; background:repeating-linear-gradient(90deg,transparent 0 48px,rgba(130,112,86,.08) 48px 49px); }
        .layout-content { position:relative; } .layout-card h3 { margin:0; font-size:1.1rem; } .layout-score { color:var(--ink); font:700 1.7rem 'Space Grotesk'; margin:1.1rem 0 .1rem; }
        .status { display:inline-block; border-radius:99px; padding:.27rem .6rem; font-size:.68rem; font-weight:700; } .status.healthy { background:#dbe9db; color:var(--green); } .status.review { background:#f3e3bd; color:var(--amber); } .status.priority { background:#f1d4cd; color:var(--red); }
        .mini-shelf { display:flex; align-items:end; gap:4px; height:60px; border-bottom:6px solid #a99678; margin-top:1rem; padding:0 8px 5px; }
        .mini-shelf i { display:block; width:14px; height:34px; border-radius:2px 2px 0 0; background:var(--orange); } .mini-shelf i:nth-child(2n) { background:var(--green); height:45px; } .mini-shelf i:nth-child(3n) { background:#d3a45b; height:27px; } .mini-shelf i.empty { background:transparent; border:1px dashed #a99678; }
        .insight { border-left:3px solid var(--orange); padding:.8rem 1rem; background:#fff7ed; color:#5f4029; font-size:.85rem; }
        .page-title { padding:2.8rem 0 1.6rem; } .page-title h1 { font-size:3.5rem; margin-bottom:.6rem; } .footer-note { text-align:center; color:#777269; font-size:.75rem; padding:3rem 0 1rem; }
        .auth-shell { min-height:82vh; display:flex; align-items:flex-start; } .auth-visual { background:#2d2c27; border-radius:16px 0 0 16px; min-height:560px; height:100%; padding:3rem; color:#fff9ef; position:relative; overflow:hidden; }
        .auth-visual h1, .auth-visual p { color:#fff9ef !important; } .auth-visual p { opacity:.82; max-width:350px; } .auth-visual:after { content:'AISLE 04  /  SMARTER PLACEMENT  /  STORE 014'; position:absolute; left:3rem; bottom:3rem; color:#e7b16b; font-size:.7rem; letter-spacing:1.7px; }
        [data-testid="stVerticalBlockBorderWrapper"] { background:var(--panel); border:1px solid var(--line); border-radius:0 16px 16px 0; min-height:560px; height:100%; padding:2.5rem 3rem; margin:0; }
        .upload-placeholder { background:#eee8dc; border:1px dashed #b8a98f; border-radius:12px; min-height:300px; display:grid; place-items:center; text-align:center; padding:2rem; }
        .upload-placeholder strong { color:var(--ink); display:block; font:700 1.2rem 'Space Grotesk'; margin-bottom:.5rem; }
        .uploaded-photo { border-radius:12px; border:1px solid var(--line); background:#e8e0d4; padding:.6rem; }
        .demo-label { display:inline-block; background:#f0e2c8; color:#765522; border-radius:99px; padding:.25rem .6rem; font-size:.68rem; font-weight:700; letter-spacing:.5px; }
        .photo-panel { min-height:440px; border-radius:14px; overflow:hidden; position:relative; background:#7b6e5f center/cover no-repeat; box-shadow:0 18px 50px rgba(69,57,40,.16); }
        .photo-panel:after { content:''; position:absolute; inset:0; background:linear-gradient(180deg,rgba(19,18,15,.05),rgba(19,18,15,.68)); }
        .photo-panel-copy { position:absolute; z-index:1; left:2rem; right:2rem; bottom:1.6rem; color:#fffdf8; }
        .photo-panel-copy strong { display:block; color:#fffdf8; font:700 1.45rem 'Space Grotesk'; }
        .photo-panel-copy span { color:#f5eee3; font-size:.8rem; }
        .photo-banner { min-height:260px; border-radius:14px; overflow:hidden; position:relative; background:#7b6e5f center/cover no-repeat; }
        .photo-banner:after { content:''; position:absolute; inset:0; background:linear-gradient(90deg,rgba(18,17,14,.72),rgba(18,17,14,.08)); }
        .photo-banner-copy { position:absolute; z-index:1; left:2rem; top:2rem; max-width:430px; }
        .photo-banner-copy h2, .photo-banner-copy p { color:#fffdf8 !important; }
        .section-thumb { height:92px; border-radius:8px; background:center/cover no-repeat; margin-bottom:1rem; position:relative; overflow:hidden; }
        .section-thumb:after { content:''; position:absolute; inset:0; background:linear-gradient(180deg,transparent,rgba(20,18,14,.28)); }
        .upload-placeholder { background:#777066 center/cover no-repeat; min-height:420px; border:0; position:relative; overflow:hidden; }
        .upload-placeholder:before { content:''; position:absolute; inset:0; background:linear-gradient(180deg,rgba(22,20,16,.15),rgba(22,20,16,.72)); }
        .upload-placeholder > div { position:relative; z-index:1; color:#fffdf8; }
        .upload-placeholder strong { color:#fffdf8; }
        .upload-placeholder span { color:#f5eee3; }
        .auth-visual { background:#777066 center/cover no-repeat; }
        .auth-visual:before { content:''; position:absolute; inset:0; background:linear-gradient(90deg,rgba(22,20,16,.78),rgba(22,20,16,.3)); }
        .auth-visual > * { position:relative; z-index:1; }
        .auth-visual:after { z-index:1; }
        .auth-visual h1 { text-shadow:0 2px 18px rgba(0,0,0,.25); }
        [data-testid="stVerticalBlockBorderWrapper"] label, [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stWidgetLabel"] p { color:var(--ink) !important; font-weight:600; }
        .analysis-heading h2, .analysis-section h2 { color:#17202a !important; margin:.35rem 0 1rem; }
        .analysis-metric { background:var(--panel); border:1px solid var(--line); border-top:4px solid var(--orange); border-radius:10px; padding:1rem; min-height:92px; }
        .analysis-metric span { display:block; color:#333; font-size:.68rem; font-weight:700; letter-spacing:.5px; text-transform:uppercase; }
        .analysis-metric strong { display:block; color:#17202a; font:700 1.45rem 'Space Grotesk'; margin-top:.45rem; }
        .analysis-section { margin-top:2rem; }
        .analysis-summary { background:#fffaf1; border-left:4px solid var(--orange); color:#303030; border-radius:0 8px 8px 0; padding:1rem 1.15rem; line-height:1.65; }
        .analysis-item, .analysis-action { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:1rem 1.15rem; margin:.75rem 0; }
        .analysis-item h3 { color:#202020 !important; font-size:1.05rem; margin:.65rem 0 .4rem; }
        .analysis-item p, .analysis-action p { color:#303030 !important; font-size:.88rem; line-height:1.55; margin:.3rem 0; }
        .analysis-action strong { color:#202020; display:block; margin:.65rem 0 .2rem; }
        .analysis-badge { display:inline-block; border-radius:99px; padding:.25rem .6rem; font-size:.67rem; font-weight:700; text-transform:uppercase; }
        .analysis-high { background:#f1d4cd; color:#963f31; } .analysis-medium { background:#f3e3bd; color:#8d651b; } .analysis-low { background:#dbe9db; color:#3f6749; }
        [data-testid="stRadio"] label, [data-testid="stRadio"] label p { color:#303030 !important; }
        [data-testid="stFileUploader"] label, [data-testid="stFileUploader"] small { color:#333 !important; }
        .empty-state { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:2rem; min-height:270px; }
        .empty-state h2 { color:#17202a !important; margin:.35rem 0 .65rem; }
        .empty-state p { color:#303030 !important; max-width:620px; line-height:1.65; }
        .history-card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:.8rem; height:100%; }
        .history-card img { width:100%; height:150px; object-fit:cover; border-radius:8px; }
        .history-card h3 { color:#202020 !important; font-size:1rem; margin:.7rem 0 .25rem; }
        .history-score { color:#17202a; font:700 1.8rem 'Space Grotesk'; }
        .history-meta { color:#4a4a4a; font-size:.75rem; line-height:1.5; }

        .action-step-card { display:flex; gap:1rem; align-items:flex-start; background:var(--panel); border:1px solid var(--line); border-left:5px solid var(--orange); border-radius:12px; padding:1rem 1.1rem; margin:.7rem 0; }
        .action-step-number { min-width:34px; height:34px; border-radius:50%; background:var(--orange); color:#fffdf8; display:grid; place-items:center; font-weight:700; }
        .action-step-label { color:var(--orange-dark); font-size:.68rem; font-weight:700; text-transform:uppercase; letter-spacing:1px; margin-bottom:.25rem; }
        .action-step-body strong { color:#202020; font-size:1rem; }
        .action-step-body p { color:#303030 !important; margin:.35rem 0 0; font-size:.86rem; line-height:1.55; }
        .visual-before-after { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:1rem; }
        @media (max-width:1100px) { .block-container { padding-top:1.25rem; } .hero-copy { padding:2.25rem 0 1rem; } .hero-copy h1 { font-size:34px; } .photo-panel { min-height:320px; } }
        @media (max-width:900px) { .block-container { padding:1.25rem 1rem 3rem; } .hero-copy { padding:2rem 0 1rem; } .hero-copy h1 { font-size:38px; } .shelf-scene { min-height:350px; } .auth-visual { border-radius:16px 16px 0 0; min-height:360px; height:auto; } [data-testid="stVerticalBlockBorderWrapper"] { border-radius:0 0 16px 16px; min-height:auto; height:auto; padding:2rem 1.25rem; } }
        @media (max-width:600px) { .hero-copy h1 { font-size:34px; } .hero-copy p { font-size:1rem; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_session() -> None:
    defaults = {"authenticated": False, "auth_mode": "login", "page": "Home", "shelf_image": None, "shelf_image_name": "", "shelf_image_mime": "", "shelf_goal": "Overall Shelf Review", "shelf_analysis": None, "analysis_source": "", "shelf_analyses": [], "selected_scenario": SCENARIO_OPTIONS[0], "scenario_actions": [], "analysis_error_message": "", "analysis_retry_available": False, "analysis_retry_label": "Try Analysis Again", "language": "English"}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def analysis_record_to_model(record: dict):
    analysis = record["analysis"]
    if hasattr(analysis, "model_dump"):
        return analysis
    from models.shelf_analysis import ShelfAnalysis

    return ShelfAnalysis.model_validate(analysis)


def save_analysis_record(analysis, image_bytes: bytes, image_name: str, image_mime: str, goal: str, section: str) -> None:
    record = {
        "id": str(uuid4()),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "image": image_bytes,
        "image_name": image_name,
        "image_mime": image_mime,
        "goal": goal,
        "section": section,
        "analysis": analysis,
    }
    st.session_state.shelf_analyses.append(record)


def latest_real_record() -> dict | None:
    return st.session_state.shelf_analyses[-1] if st.session_state.shelf_analyses else None


def render_no_analysis_state(title: str, body: str) -> None:
    st.markdown(f'<div class="empty-state"><h2>{html.escape(title)}</h2><p>{html.escape(body)}</p></div>', unsafe_allow_html=True)
    if st.button("Inspect a Shelf →", type="primary", key=f"inspect_from_{st.session_state.page}"):
        st.session_state.page = "Inspect Shelf"
        st.rerun()


def reset_main_scroll() -> None:
    components.html(
        """
        <script>
        const main = window.parent.document.querySelector('section[data-testid="stMain"]');
        if (main) main.scrollTop = 0;
        </script>
        """,
        height=0,
    )


def render_language_selector() -> dict:
    language_options = list(UI_TEXT.keys())
    current_language = st.session_state.get("language", "English")
    selected = st.selectbox(
        "🌐 Language / భాష / भाषा",
        language_options,
        index=language_options.index(current_language),
        key="global_language",
    )
    st.session_state.language = selected
    return UI_TEXT[selected]


def render_action_cards(analysis, t: dict) -> None:
    actions = analysis.priority_actions or analysis.recommendations
    st.markdown(
        f'<div class="analysis-section"><h2>{html.escape(t["what_change"])}</h2>'
        '<p>Follow these simple steps on the real shelf.</p></div>',
        unsafe_allow_html=True,
    )
    if not actions:
        st.info("No clear shelf change was recommended from the visible photo.")
        return

    for index, item in enumerate(actions, start=1):
        action = html.escape(item.action)
        reason = html.escape(item.reason)
        st.markdown(
            f'<div class="action-step-card">'
            f'<div class="action-step-number">{index}</div>'
            f'<div class="action-step-body">'
            f'<div class="action-step-label">{html.escape(t["step"])} {index}</div>'
            f'<strong>{action}</strong>'
            f'<p>{reason}</p>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

def render_auth() -> None:
    left, right = st.columns([1.22, 1], gap="small")
    with left:
        login_image = html.escape(image_source("login"), quote=True)
        st.markdown(f'<div class="auth-visual" style="background-image:url(\'{login_image}\')"><div class="brand-mark">SS</div><h1 style="font-size:3.3rem;margin-top:3rem">ShelfSight</h1><p style="font-size:1.2rem">Smarter shelves. Better stores.</p><p style="margin-top:2rem">AI-powered retail merchandising intelligence for modern stores.</p></div>', unsafe_allow_html=True)
    with right:
        with st.container(border=True):
            if st.session_state.auth_mode == "login":
                st.markdown('<div class="eyebrow">Store team access</div><h2>Welcome back</h2><p>Sign in to continue managing your store.</p>', unsafe_allow_html=True)
                with st.form("login_form"):
                    st.text_input("Email", placeholder="you@store.com")
                    st.text_input("Password", type="password", placeholder="Enter your password")
                    if st.form_submit_button("Login", type="primary", use_container_width=True):
                        st.session_state.authenticated = True
                        st.rerun()
                st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
                st.markdown("Don't have an account?")
                if st.button("Create account", use_container_width=True):
                    st.session_state.auth_mode = "signup"
                    st.rerun()
            else:
                st.markdown('<div class="eyebrow">Set up your store workspace</div><h2>Create your ShelfSight account</h2>', unsafe_allow_html=True)
                with st.form("signup_form"):
                    st.text_input("Full Name")
                    st.text_input("Email")
                    st.text_input("Password", type="password")
                    st.text_input("Store / Organization")
                    st.selectbox("Role", ["Store Manager", "Merchandising Manager", "Category Manager", "Store Staff"])
                    if st.form_submit_button("Create Account", type="primary", use_container_width=True):
                        st.session_state.authenticated = True
                        st.rerun()
                st.markdown("Already have an account?")
                if st.button("Login", use_container_width=True):
                    st.session_state.auth_mode = "login"
                    st.rerun()


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown('<div class="brand-lockup"><span class="brand-mark">SS</span><span class="brand-name">ShelfSight</span><div class="brand-sub">Retail merchandising intelligence</div></div>', unsafe_allow_html=True)
        st.caption("NORTHSTAR MARKET  /  STORE 014")
        current = st.session_state.page
        for group, items in NAV_GROUPS.items():
            st.markdown(f'<div class="nav-group">{group}</div>', unsafe_allow_html=True)
            for icon, label in items:
                page = PAGE_BY_LABEL[label]
                if st.button(f"{icon}  {label}", key=f"nav_{label}", type="primary" if page == current else "secondary", use_container_width=True):
                    st.session_state.page = page
                    st.rerun()
        st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)
        st.markdown("<div class='brand-sub'>Store scan status</div>", unsafe_allow_html=True)
        st.markdown("<div style='color:#dce7d7;font-size:.85rem;margin-top:.45rem'>● Synced 12 min ago</div>", unsafe_allow_html=True)
        if st.button("Sign out", key="sign_out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.auth_mode = "login"
            st.rerun()
    return current


def render_photo_panel(key: str, label: str, detail: str, class_name: str = "photo-panel") -> None:
    photo = html.escape(image_source(key), quote=True)
    st.markdown(f'<div class="{class_name}" style="background-image:url(\'{photo}\')"><div class="photo-panel-copy"><strong>{html.escape(label)}</strong><span>{html.escape(detail)}</span></div></div>', unsafe_allow_html=True)


def render_home() -> None:
    left, right = st.columns([1.22, 1], gap="large")
    with left:
        st.markdown('<div class="hero-copy"><div class="eyebrow">Store intelligence, made tangible</div><h1>Turn Every Shelf Into a<br>Smarter Store.</h1><p>ShelfSight helps retail teams analyze shelf presentation, discover merchandising opportunities, simulate improvements, and track store evolution.</p></div>', unsafe_allow_html=True)
        actions = st.columns([1, 1, 1.25])
        with actions[0]:
            if st.button("Inspect My Shelf  ->", type="primary", use_container_width=True):
                st.session_state.page = "Inspect Shelf"
                st.rerun()
        with actions[1]:
            if st.button("Explore Demo Store", use_container_width=True):
                st.session_state.page = "Demo Store"
                st.rerun()
        st.markdown('<div class="hero-note"><span></span> Live merchandising view / Store 014</div>', unsafe_allow_html=True)
    with right:
        render_photo_panel("hero", "A better read of every aisle", "Real retail presentation / Store 014")
    st.markdown('<div class="section-heading"><div><div class="eyebrow">DEMO STORE / Example snapshot</div><h2>Merchandising, in context.</h2></div><div class="metric-detail">Predefined demo data</div></div>', unsafe_allow_html=True)
    cols = st.columns(4, gap="medium")
    for col, label, value, detail in zip(cols, ["Shelf Health / Demo", "Visible Product Presence / Demo", "Visibility / Demo", "Space Utilization / Demo"], ["84", "89%", "78", "91%"], ["Example score", "Visible facings only", "Example score", "Example score"]):
        with col:
            st.markdown(f'<div class="panel metric-panel"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-detail">{detail}</div></div>', unsafe_allow_html=True)


def render_metric_strip() -> None:
    cols = st.columns(5, gap="small")
    metrics = [("Shelf Health / Demo", "84", "+6 this week"), ("Visible Product Presence / Demo", "89%", "Visible facings"), ("Visibility / Demo", "78", "Needs review"), ("Organization / Demo", "86", "On plan"), ("Space Utilization / Demo", "91%", "Strong")]
    for col, (label, value, detail) in zip(cols, metrics):
        with col:
            st.markdown(f'<div class="panel metric-panel"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-detail">{detail}</div></div>', unsafe_allow_html=True)


def render_layout() -> None:
    st.markdown('<div class="section-heading"><div><div class="eyebrow">Store floor / current read</div><h2>Virtual Store Layout</h2></div><div class="metric-detail">5 merchandising zones / demo data</div></div>', unsafe_allow_html=True)
    cols = st.columns(3, gap="medium")
    for index, section in enumerate(SECTIONS):
        with cols[index % 3]:
            bars = "".join('<i class="empty"></i>' if i == section["issues"] % 5 else "<i></i>" for i in range(8))
            issue_word = "issue" if section["issues"] == 1 else "issues"
            image_key = section["name"].lower().replace(" ", "_")
            st.markdown(f'<div class="layout-card"><div class="layout-content"><div class="section-thumb" style="background-image:url(\'{html.escape(image_source(image_key), quote=True)}\')"></div><h3>{section["name"]}</h3><div class="metric-detail">{section["accent"]}</div><div class="layout-score">{section["score"]}<span style="font:500 .8rem DM Sans;color:#59564f"> / 100</span></div><span class="status {section["tone"]}">{section["status"]}</span><div class="mini-shelf">{bars}</div><div style="font-size:.7rem;color:#59564f;margin-top:.55rem">{section["issues"]} detected {issue_word}</div></div></div>', unsafe_allow_html=True)


def render_demo_store() -> None:
    st.markdown('<div class="page-title"><div class="eyebrow">DEMO STORE / Tuesday, 22 September 2026</div><h1>Good morning, Store Manager</h1><p>Example merchandising data for exploring the ShelfSight experience.</p><span class="demo-label">DEMO STORE DATA / NOT YOUR STORE DATA</span></div>', unsafe_allow_html=True)
    left, right = st.columns([.75, 1.25], gap="large")
    with left:
        st.markdown('<div class="panel" style="min-height:230px"><div class="metric-label">Store Health</div><div style="display:flex;align-items:center;gap:1.4rem;margin-top:1rem"><div class="health-ring"><div class="health-score">84<small>out of 100</small></div></div><div><div style="font-weight:700;font-size:1.05rem;color:#26241f">Trading ready</div><p style="font-size:.8rem;line-height:1.5">Presentation is strong across core aisles. Prioritize Personal Care next.</p><span class="status healthy">+6 vs last scan</span></div></div></div>', unsafe_allow_html=True)
    with right:
        render_photo_panel("store", "Northstar Market / Store 014", "Current store floor / demo imagery", "photo-banner")
    st.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
    render_metric_strip()
    render_layout()
    st.markdown('<div class="section-heading"><div><div class="eyebrow">Recommended Actions</div><h2>Make the next move count.</h2></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="insight"><strong>Priority Shelf / Personal Care</strong><br>Restore two missing facings and move the travel-size display into the eye-level band. This is a demo recommendation for the prototype.</div>', unsafe_allow_html=True)


def render_user_layout(records: list[dict]) -> None:
    st.markdown('<div class="section-heading"><div><div class="eyebrow">My Store / analyzed sections</div><h2>Your Shelf Layout</h2></div></div>', unsafe_allow_html=True)
    if not records:
        st.markdown('<div class="empty-state"><div class="eyebrow">MY STORE</div><h2>Your store layout will appear here after you analyze your first shelf.</h2><p>Each analyzed shelf becomes a real section using its uploaded photograph and AI-generated merchandising metrics.</p></div>', unsafe_allow_html=True)
        return
    columns = st.columns(min(3, len(records)), gap="medium")
    for index, record in enumerate(records):
        analysis = analysis_record_to_model(record)
        with columns[index % len(columns)]:
            st.markdown('<div class="history-card">', unsafe_allow_html=True)
            st.image(record["image"], use_container_width=True)
            st.markdown(
                f'<h3>{html.escape(record["section"])}</h3>'
                f'<div class="history-meta">{html.escape(record["image_name"])}<br>'
                f'Analyzed {html.escape(record["timestamp"].replace("T", " "))}</div>',
                unsafe_allow_html=True,
            )
            st.markdown('</div>', unsafe_allow_html=True)


def render_my_store() -> None:
    records = st.session_state.shelf_analyses
    st.markdown('<div class="page-title"><div class="eyebrow">MY STORE / Your analyzed shelves</div><h1>Your store starts here.</h1><p>My Store contains only shelves you have uploaded and analyzed.</p></div>', unsafe_allow_html=True)
    if not records:
        left, right = st.columns([1.15, .85], gap="large")
        with left:
            st.markdown('<div class="empty-state"><div class="eyebrow">MY STORE</div><h2>No shelves analyzed yet.</h2><p>Upload your first shelf photo and ShelfSight will build your merchandising intelligence dashboard from real analysis.</p></div>', unsafe_allow_html=True)
            if st.button("Inspect Your First Shelf →", type="primary", key="first_shelf_button"):
                st.session_state.page = "Inspect Shelf"
                st.rerun()
        with right:
            render_photo_panel("shelf", "Your store intelligence will appear here", "Illustrative retail image / no user metrics yet")
        return

    latest = records[-1]
    analysis = analysis_record_to_model(latest)
    st.markdown(f'<span class="demo-label">{len(records)} REAL SHELF ANALYSIS{"ES" if len(records) != 1 else ""}</span>', unsafe_allow_html=True)
    left, right = st.columns([.9, 1.1], gap="large")
    with left:
        st.image(latest["image"], caption=latest["image_name"], use_container_width=True)
    with right:
        st.markdown('<div class="eyebrow">Your Latest Shelf Analysis</div><h2 style="color:#17202a !important">AI Shelf Analysis</h2>', unsafe_allow_html=True)
        st.markdown(
            '<div class="analysis-summary">Your latest real shelf photo and its improvement guidance are ready. '
            'Open Improve My Shelf to see the visual changes.</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Last analyzed: {latest['timestamp'].replace('T', ' ')} / {latest['section']}")
        if st.button("View Full Analysis →", key="view_latest_analysis"):
            st.session_state.page = "Inspect Shelf"
            st.session_state.shelf_image = latest["image"]
            st.session_state.shelf_image_name = latest["image_name"]
            st.session_state.shelf_image_mime = latest["image_mime"]
            st.session_state.shelf_analysis = analysis
            st.rerun()
    render_user_layout(records)


def render_store_evolution() -> None:
    records = st.session_state.shelf_analyses
    st.markdown(
        '<div class="page-title"><div class="eyebrow">STORE EVOLUTION / Real analysis history</div>'
        '<h1>Store Progress</h1><p>Compare real shelf photos and see what changed.</p></div>',
        unsafe_allow_html=True,
    )
    render_language_selector()

    if not records:
        st.markdown(
            '<div class="empty-state"><h2>No shelf history yet.</h2>'
            '<p>Analyze a shelf to start tracking your store progress.</p></div>',
            unsafe_allow_html=True,
        )
        return

    if len(records) == 1:
        st.markdown(
            '<div class="empty-state"><h2>Your first shelf scan is complete.</h2>'
            '<p>Make the suggested changes, then take another photo of the same shelf. '
            'ShelfSight will show the two real photos together.</p></div>',
            unsafe_allow_html=True,
        )
        st.image(records[-1]["image"], caption="Latest shelf photo", use_container_width=True)
        return

    previous_record = records[-2]
    latest_record = records[-1]
    previous = analysis_record_to_model(previous_record)
    latest = analysis_record_to_model(latest_record)

    st.markdown(
        '<div class="analysis-section"><h2>Before and After</h2>'
        '<p>Look at the real shelf photos before and after your changes.</p></div>',
        unsafe_allow_html=True,
    )
    before_col, after_col = st.columns(2, gap="large")
    with before_col:
        st.markdown('<div class="eyebrow">BEFORE</div>', unsafe_allow_html=True)
        st.image(previous_record["image"], caption=previous_record["image_name"], use_container_width=True)
    with after_col:
        st.markdown('<div class="eyebrow">AFTER</div>', unsafe_allow_html=True)
        st.image(latest_record["image"], caption=latest_record["image_name"], use_container_width=True)

    previous_actions = {item.action for item in (previous.priority_actions or previous.recommendations)}
    latest_actions = [item.action for item in (latest.priority_actions or latest.recommendations)]
    changed = [action for action in latest_actions if action not in previous_actions]

    st.markdown('<div class="analysis-section"><h2>What changed?</h2></div>', unsafe_allow_html=True)
    if changed:
        for action in changed:
            st.markdown(f"- {html.escape(action)}")
    else:
        st.markdown(
            '<div class="analysis-summary">The latest scan has been saved. '
            'Review the two photos above to verify the shelf changes.</div>',
            unsafe_allow_html=True,
        )

    st.caption(
        f"Before: {previous_record['timestamp'].replace('T', ' ')}  ·  "
        f"After: {latest_record['timestamp'].replace('T', ' ')}"
    )

    if st.button("📷 Take another photo", type="primary", key="progress_new_photo"):
        st.session_state.page = "Inspect Shelf"
        st.session_state.shelf_analysis = None
        st.session_state.analysis_source = ""
        st.rerun()

def render_inspect_shelf() -> None:
    render_language_selector()
    st.markdown('<div class="page-title"><div class="eyebrow">Merchandising / Store scan</div><h1 style="color:#17202A !important">Inspect a Shelf</h1><p style="color:#303030">Upload a photo of your store shelf to discover merchandising opportunities.</p></div>', unsafe_allow_html=True)
    left, right = st.columns([.88, 1.12], gap="large")
    with left:
        st.markdown('<div class="eyebrow">Step 1</div><h2 style="color:#202020 !important">Upload Shelf Photo</h2><p style="color:#303030">Use a clear photo showing the full shelf, product labels, and any empty positions.</p>', unsafe_allow_html=True)
        uploaded = st.file_uploader("Choose a shelf photo", type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed")
        if uploaded is not None:
            uploaded_bytes = uploaded.getvalue()
            if uploaded_bytes != st.session_state.shelf_image or uploaded.name != st.session_state.shelf_image_name:
                st.session_state.shelf_image = uploaded_bytes
                st.session_state.shelf_image_name = uploaded.name
                st.session_state.shelf_image_mime = uploaded.type or "image/jpeg"
                st.session_state.shelf_analysis = None
                st.session_state.analysis_source = ""
                st.session_state.analysis_error_message = ""
                st.session_state.analysis_retry_available = False
                st.session_state.analysis_retry_label = "Try Analysis Again"
            st.success(f"Shelf photo ready: {uploaded.name}")
        st.markdown('<div class="eyebrow" style="margin-top:2rem">Step 2</div><h2 style="color:#202020 !important">Choose Your Goal</h2>', unsafe_allow_html=True)
        goal = st.radio("What would you like to improve?", ["Overall Shelf Review", "Improve Product Visibility", "Reduce Empty Space", "Improve Organization", "Highlight Promotional Products"], label_visibility="collapsed")
        st.session_state.shelf_goal = goal
        section = st.selectbox("Shelf Section", ["Beverages", "Snacks", "Grocery", "Personal Care", "Premium Display", "Other"], key="shelf_section")
        st.markdown('<div class="eyebrow" style="margin-top:1.4rem;color:#333">Step 3</div>', unsafe_allow_html=True)
        analyze_requested = st.button("Analyze My Shelf →", type="primary", use_container_width=True)
        retry_requested = False
        if st.session_state.analysis_error_message:
            st.error(st.session_state.analysis_error_message)
            if st.session_state.analysis_retry_available:
                retry_requested = st.button(st.session_state.analysis_retry_label, type="primary", use_container_width=True)
        if analyze_requested or retry_requested:
            if st.session_state.shelf_image is None:
                st.warning("Upload a shelf photo first so we know what to inspect.")
            else:
                with st.status("Analyzing your shelf...", expanded=False) as analysis_status:
                    try:
                        analysis, analysis_source = analyze_shelf(
                            st.session_state.shelf_image,
                            st.session_state.shelf_image_mime,
                            goal,
                            status_callback=lambda message: analysis_status.update(label=message),
                        )

                        st.session_state.shelf_analysis = analysis
                        st.session_state.analysis_source = analysis_source

                        save_analysis_record(analysis, st.session_state.shelf_image, st.session_state.shelf_image_name, st.session_state.shelf_image_mime, goal, section)
                        st.session_state.analysis_error_message = ""
                        st.session_state.analysis_retry_available = False
                        st.session_state.analysis_retry_label = "Try Analysis Again"
                        analysis_status.update(
                            label=(
                                "Demo analysis ready."
                                if analysis_source == "demo"
                                else "AI analysis complete."
                            ),
                            state="complete",
                        )
                    except AnalysisError as exc:
                        st.session_state.shelf_analysis = None
                        st.session_state.analysis_error_message = str(exc)
                        st.session_state.analysis_retry_available = getattr(exc, "retryable", False)
                        st.session_state.analysis_retry_label = getattr(exc, "retry_label", "Try Analysis Again")
                        analysis_status.update(label="Analysis unavailable.", state="error")
                        st.rerun()
    with right:
        if st.session_state.shelf_image:
            st.markdown('<div class="eyebrow" style="color:#333">Your Shelf</div>', unsafe_allow_html=True)
            st.markdown('<div class="uploaded-photo">', unsafe_allow_html=True)
            st.image(st.session_state.shelf_image, caption=st.session_state.shelf_image_name, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            placeholder = html.escape(image_source("shelf"), quote=True)
            st.markdown(f'<div class="upload-placeholder" style="background-image:url(\'{placeholder}\')"><div><strong>Your shelf photo will appear here</strong><span>Start with a well-lit image of one shelf or display.</span><br><span style="font-size:.75rem;color:#f5eee3">JPG, JPEG, PNG, or WEBP</span></div></div>', unsafe_allow_html=True)
    if st.session_state.shelf_analysis is not None:
        st.markdown('<div style="margin-top:2.5rem"></div>', unsafe_allow_html=True)

        if st.session_state.analysis_source == "demo":
            st.info(
                "Demo analysis — Gemini is temporarily unavailable. "
                "This sample result is clearly labeled and is not a reading of this photo."
            )

        render_analysis_results(st.session_state.shelf_analysis)


def render_improve_shelf() -> None:
    record = latest_real_record()
    t = UI_TEXT.get(st.session_state.get("language", "English"), UI_TEXT["English"])

    st.markdown(
        '<div class="page-title"><div class="eyebrow">MY STORE / Shelf improvement</div>'
        '<h1>Improve My Shelf</h1><p>See what to change on your real shelf, step by step.</p></div>',
        unsafe_allow_html=True,
    )
    render_language_selector()

    if record is None:
        render_no_analysis_state(
            "Analyze a shelf first",
            "Upload a real shelf photo to see personalized improvement suggestions.",
        )
        return

    analysis = analysis_record_to_model(record)

    st.markdown(
        f'<div class="analysis-section"><h2>{html.escape(t["your_shelf"])}</h2>'
        '<p>This is the real photo you uploaded.</p></div>',
        unsafe_allow_html=True,
    )
    st.image(record["image"], caption=record["image_name"], use_container_width=True)

    st.markdown(
        f'<div class="analysis-section"><h2>{html.escape(t["what_found"])}</h2></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="analysis-summary">{html.escape(analysis.summary)}</div>',
        unsafe_allow_html=True,
    )

    render_action_cards(analysis, t)

    st.markdown(
        f'<div class="analysis-section"><h2>{html.escape(t["before_after"])}</h2>'
        '<p>The visual planner below shows how the shelf could be arranged.</p></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="visual-before-after">', unsafe_allow_html=True)
    render_current_vs_recommended(record["image"], analysis)
    st.markdown('</div>', unsafe_allow_html=True)

    render_shelf_heatmap(record["image"], analysis)
    render_zone_guide(analysis)

    reasons = [item.reason for item in (analysis.priority_actions or analysis.recommendations)]
    st.markdown(
        f'<div class="analysis-section"><h2>{html.escape(t["why"])}</h2></div>',
        unsafe_allow_html=True,
    )
    if reasons:
        st.markdown(
            f'<div class="analysis-summary">{html.escape(" ".join(reasons))}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("There is not enough visible evidence to explain a layout change.")

    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    fixed_col, photo_col = st.columns(2, gap="medium")
    with fixed_col:
        if st.button(f"✓ {t['fixed']}", type="primary", use_container_width=True, key="improve_fixed"):
            st.session_state.page = "Inspect Shelf"
            st.session_state.shelf_analysis = None
            st.session_state.analysis_source = ""
            st.session_state.analysis_error_message = ""
            st.session_state.analysis_retry_available = False
            st.rerun()
    with photo_col:
        if st.button(f"📷 {t['take_photo']}", use_container_width=True, key="improve_take_photo"):
            st.session_state.page = "Inspect Shelf"
            st.session_state.shelf_analysis = None
            st.session_state.analysis_source = ""
            st.session_state.analysis_error_message = ""
            st.session_state.analysis_retry_available = False
            st.rerun()

def render_try_scenario() -> None:
    render_language_selector()
    record = latest_real_record()
    st.markdown(
        '<div class="page-title"><div class="eyebrow">MY STORE / What-if planning</div><h1>Try a Scenario</h1><p>See how a shelf change could affect the layout.</p></div>',
        unsafe_allow_html=True,
    )

    if record is None:
        render_no_analysis_state(
            "Analyze a shelf first to try a scenario.",
            "A scenario needs a real shelf analysis.",
        )
        return

    analysis = analysis_record_to_model(record)

    scenario = st.selectbox(
        "What would you like to change?",
        SCENARIO_OPTIONS,
        key="selected_scenario",
    )

    st.markdown(
        '<div class="analysis-section"><h2>Interactive Shelf Planner</h2></div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "Choose a change above, then review the model-based visual estimate below."
    )

    render_scenario_comparison(
        record["image"],
        analysis,
        scenario,
    )

    if st.button("Save Improvement Plan", key="save_scenario_plan"):
        st.session_state.scenario_actions = [scenario]
        st.success(
            "Improvement plan saved for this session. Recheck the real shelf after making the change."
        )


def render_challenges() -> None:
    records = st.session_state.shelf_analyses
    st.markdown(
        '<div class="page-title"><div class="eyebrow">MY STORE / Real shelf goals</div><h1>Challenges</h1><p>Choose a real shelf problem to improve and verify it with a new photo.</p></div>',
        unsafe_allow_html=True,
    )

    if not records:
        render_no_analysis_state(
            "No shelf analysis yet.",
            "Analyze a shelf first to create a real challenge.",
        )
        return

    latest = analysis_record_to_model(records[-1])
    issues = latest.detected_issues

    if not issues:
        st.info("No visible problems were found in the latest real shelf analysis.")
        return

    for index, issue in enumerate(issues):
        with st.container(border=True):
            st.markdown(
                f"**{issue.severity} priority:** {html.escape(issue.issue)}"
            )
            st.write(f"Why it matters: {issue.evidence}")
            st.write(f"What to do: {issue.recommendation}")
            st.caption(
                "This challenge is complete only after a new real shelf photo is analyzed."
            )

            if st.button("Analyze New Photo", key=f"challenge_{index}"):
                st.session_state.page = "Inspect Shelf"
                st.rerun()

def render_copilot() -> None:
    records = st.session_state.shelf_analyses
    st.markdown('<div class="page-title"><div class="eyebrow">MY STORE / Real shelf helper</div><h1>ShelfSight Copilot</h1><p>Ask about your saved shelf analysis.</p></div>', unsafe_allow_html=True)
    if not records:
        render_no_analysis_state("No shelf analysis yet.", "Analyze a shelf first so Copilot can use your real shelf data.")
        return
    analysis = analysis_record_to_model(records[-1])
    question = st.selectbox("What would you like to know?", ["What should I fix first?", "Why is my score low?", "Which shelf area needs attention?", "How can I improve this shelf?", "Why did you move this product group?"])
    if question == "What should I fix first?":
        answer = analysis.priority_actions[0].action if analysis.priority_actions else (analysis.detected_issues[0].recommendation if analysis.detected_issues else "No immediate problem was found in the latest photo.")
    elif question == "Why is my score low?":
        answer = analysis.detected_issues[0].evidence if analysis.detected_issues else "The latest shelf score is based on what was visible in the uploaded photo."
    elif question == "Which shelf area needs attention?":
        answer = analysis.detected_issues[0].evidence if analysis.detected_issues else "No specific shelf area was marked as needing attention."
    elif question == "Why did you move this product group?":
        answer = "The suggested layout keeps visible product groups together and uses only positions identified in the shelf photo."
    else:
        answer = analysis.recommendations[0].action if analysis.recommendations else "Keep products together, use visible empty space, and check the shelf again after changes."
    st.markdown(f'<div class="panel"><div class="eyebrow">Based on your latest real analysis</div><h2>{html.escape(answer)}</h2></div>', unsafe_allow_html=True)


def render_reports() -> None:
    records = st.session_state.shelf_analyses
    st.markdown('<div class="page-title"><div class="eyebrow">MY STORE / Real analysis report</div><h1>Reports</h1><p>View and save reports made only from your uploaded shelf analyses.</p></div>', unsafe_allow_html=True)
    if not records:
        render_no_analysis_state("No real shelf analyses available yet.", "Analyze a shelf to generate your first report.")
        return
    lines = ["ShelfSight Real Shelf Report", "", f"Analyses: {len(records)}"]
    for record in records:
        analysis = analysis_record_to_model(record)
        lines.extend(["", f"{record['timestamp']} / {record['section']}", f"Shelf Health: {analysis.overall_score} / 100", analysis.summary])
    report = "\n".join(lines)
    st.text_area("Report preview", report, height=300)
    st.download_button("Download Real Shelf Report", report, file_name="shelfsight-real-shelf-report.txt", mime="text/plain")


def render_placeholder(page: str) -> None:
    copy = {
        "Store Evolution": ("Store Progress", "Track how shelf health changes over time across departments and seasonal campaigns."),
        "Challenges": ("Challenges", "A focused queue of shelf gaps, visibility opportunities, and high-impact store actions."),
        "ShelfSight Copilot": ("ShelfSight Copilot", "Ask focused questions about store presentation, shelf health, and practical actions for the floor team."),
        "Reports": ("Reports", "Turn store scans into clear reports for regional teams, store managers, and category owners."),
    }
    title, description = copy[page]
    st.markdown(f'<div class="page-title"><div class="eyebrow">ShelfSight / {html.escape(page)}</div><h1>{html.escape(title)}</h1><p>{html.escape(description)}</p></div>', unsafe_allow_html=True)
    left, right = st.columns([1.1, .9], gap="large")
    with left:
        st.markdown('<div class="panel" style="min-height:260px"><div class="metric-label">Demo workspace</div><h2 style="margin-top:.5rem">A clear next step for the floor team.</h2><p style="line-height:1.7">This UI foundation is ready for the next product layer. Navigation, shelf data, retail terminology, and the inspection workflow are in place.</p></div>', unsafe_allow_html=True)
    with right:
        render_photo_panel("shelf", "Retail display reference", "Use a real shelf photo to begin an inspection")


def main() -> None:
    init_session()
    inject_styles()
    if not st.session_state.authenticated:
        render_auth()
        return
    page = render_sidebar()
    if page == "Home":
        render_home()
    elif page == "My Store":
        render_my_store()
    elif page == "Demo Store":
        render_demo_store()
    elif page == "Inspect Shelf":
        render_inspect_shelf()
    elif page == "Improve Shelf":
        render_improve_shelf()
    elif page == "Try Scenario":
        render_try_scenario()
    elif page == "Store Evolution":
        render_store_evolution()
    elif page == "Challenges":
        render_challenges()
    elif page == "ShelfSight Copilot":
        render_copilot()
    elif page == "Reports":
        render_reports()
    else:
        render_placeholder(page)
    st.markdown('<div class="footer-note">ShelfSight / Retail merchandising intelligence / Demo workspace</div>', unsafe_allow_html=True)
    reset_main_scroll()


if __name__ == "__main__":
    main()