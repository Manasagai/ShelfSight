import html
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components

from components.analysis_results import render_analysis_results
from components.shelf_planner import (
    SCENARIO_OPTIONS,
    create_empty_shelf_plan_image,
    render_current_vs_recommended,
    render_scenario_comparison,
    render_shelf_plan,
    render_shelf_heatmap,
    render_zone_guide,
    scenario_scores,
    score_values,
)
from models.shelf_analysis import ShelfAnalysis, EmptyShelfPlan
from services.vision_analyzer import (
    AnalysisError,
    analyze_shelf,
    analyze_empty_shelf,
)


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
    "": [
        ("⌂", "Home"),
        ("▤", "Check My Shelf"),
        ("✦", "Plan New Shelf"),
        ("◷", "Store Progress"),
    ],
}

PAGE_BY_LABEL = {
    "Home": "Home",
    "Check My Shelf": "Check My Shelf",
    "Plan New Shelf": "Plan New Shelf",
    "Store Progress": "Store Evolution",
}

LANGUAGES = {"English": "en", "తెలుగు": "te", "हिन्दी": "hi"}
LANGUAGE_TEXT = {
    "en": {
        "home": "Home",
        "check": "Check My Shelf",
        "plan": "Plan New Shelf",
        "progress": "Store Progress",
        "language": "Language",
        "check_desc": "Analyze a shelf that already contains products.",
        "plan_desc": "Plan where products should go before you arrange the shelf.",
        "progress_desc": "Compare real shelf photos over time to track improvements.",
        "check_btn": "Check My Shelf →",
        "plan_btn": "Plan New Shelf →",
        "progress_btn": "View Store Progress →",
        "hero_title": "Turn Every Shelf Into a Smarter Store.",
        "hero_body": "Take a photo of your shelf. ShelfSight uses AI image analysis to show what needs attention or plan where new products should go.",
        "upload_check": "Upload Shelf Photo (with products)",
        "upload_plan": "Upload Empty Shelf Photo",
        "goal": "What would you like to improve?",
        "analyze": "Analyze My Shelf →",
        "generate_plan": "Generate Placement Plan →",
        "your_shelf": "Your Shelf",
        "action_guide": "AI Visual Action Guide",
        "scores": "Shelf Scores",
        "found": "What We Found",
        "do": "What to do",
        "where_put": "WHERE SHOULD I PUT EACH PRODUCT?",
    },
    "te": {
        "home": "హోమ్",
        "check": "నా షెల్ఫ్ పరిశీలన",
        "plan": "కొత్త షెల్ఫ్ ప్లాన్",
        "progress": "స్టోర్ పురోగతి",
        "language": "భాష",
        "check_desc": "ఇప్పటికే ఉత్పత్తులు ఉన్న షెల్ఫ్‌ను విశ్లేషించండి.",
        "plan_desc": "ఉత్పత్తులను సర్దేముందు ఎక్కడ ఉంచాలో ప్లాన్ చేయండి.",
        "progress_desc": "సమయంతో పాటు షెల్ఫ్ పురోగతిని పోల్చి చూడండి.",
        "check_btn": "నా షెల్ఫ్ పరిశీలించండి →",
        "plan_btn": "కొత్త షెల్ఫ్ ప్లాన్ చేయండి →",
        "progress_btn": "స్టోర్ పురోగతిని చూడండి →",
        "hero_title": "ప్రతి షెల్ఫ్‌ను మరింత మెరుగైన స్టోర్‌గా మార్చండి.",
        "hero_body": "మీ షెల్ఫ్ ఫోటో తీసి అప్‌లోడ్ చేయండి. ShelfSight స్పష్టమైన చిత్ర సూచనలను అందిస్తుంది.",
        "upload_check": "షెల్ఫ్ ఫోటో (ఉత్పత్తులతో) అప్‌లోడ్ చేయండి",
        "upload_plan": "ఖాళీ షెల్ఫ్ ఫోటో అప్‌లోడ్ చేయండి",
        "goal": "ఏది మెరుగుపరచాలి?",
        "analyze": "నా షెల్ఫ్‌ను విశ్లేషించండి →",
        "generate_plan": "ప్లేస్‌మెంట్ ప్లాన్ రూపొందించండి →",
        "your_shelf": "మీ షెల్ఫ్",
        "action_guide": "AI చిత్ర చర్యల సూచన",
        "scores": "షెల్ఫ్ స్కోర్లు",
        "found": "మేము గుర్తించినవి",
        "do": "ఏం చేయాలి",
        "where_put": "ప్రతి ఉత్పత్తిని ఎక్కడ ఉంచాలి?",
    },
    "hi": {
        "home": "होम",
        "check": "मेरी शेल्फ जांचें",
        "plan": "नई शेल्फ प्लान करें",
        "progress": "स्टोर प्रगति",
        "language": "भाषा",
        "check_desc": "ऐसी शेल्फ का विश्लेषण करें जिसमें पहले से सामान रखा है।",
        "plan_desc": "सामान रखने से पहले तय करें कि किस सामान को कहाँ रखना है।",
        "progress_desc": "समय के साथ शेल्फ में हुए सुधारों की तुलना करें।",
        "check_btn": "मेरी शेल्फ जांचें →",
        "plan_btn": "नई शेल्फ प्लान करें →",
        "progress_btn": "स्टोर प्रगति देखें →",
        "hero_title": "हर शेल्फ को एक बेहतर स्टोर बनाएं।",
        "hero_body": "अपनी शेल्फ की फोटो अपलोड करें। ShelfSight आपको आसान विजुअल गाइड देगा।",
        "upload_check": "शेल्फ फोटो (सामान के साथ) अपलोड करें",
        "upload_plan": "खाली शेल्फ फोटो अपलोड करें",
        "goal": "क्या सुधारना है?",
        "analyze": "मेरी शेल्फ का विश्लेषण करें →",
        "generate_plan": "प्लेसमेंट प्लान बनाएं →",
        "your_shelf": "आपकी शेल्फ",
        "action_guide": "AI विजुअल गाइड",
        "scores": "शेल्फ स्कोर",
        "found": "क्या मिला",
        "do": "क्या करना है",
        "where_put": "किस सामान को कहाँ रखें?",
    },
}


def t(key: str) -> str:
    return LANGUAGE_TEXT.get(st.session_state.get("language", "en"), LANGUAGE_TEXT["en"]).get(key, key)


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
    filename, fallback = RETAIL_IMAGES.get(key, RETAIL_IMAGES["shelf"])
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
        h1 { font-size:clamp(2.4rem,5vw,4.5rem); line-height:1.02; margin:.4rem 0 1.2rem; }
        h2 { font-size:1.85rem; } p, [data-testid="stMarkdownContainer"] p { color:var(--secondary); }
        .stButton button, .stDownloadButton button { border-radius:8px; font-weight:700; border:1px solid #cfc7b9; min-height:2.8rem; }
        .stButton button[kind="primary"] { background:var(--orange); color:#fffdf8; border-color:var(--orange); }
        .stTextInput input, .stSelectbox [data-baseweb="select"], .stFileUploader section { background:var(--panel); border-color:#cfc7b9; color:var(--ink); }
        .brand-lockup { padding:.5rem .25rem 1.7rem; }
        .brand-mark { display:inline-flex; width:34px; height:34px; align-items:center; justify-content:center; background:#e66f32; color:#fff8ef; font:700 13px 'Space Grotesk'; margin-right:.55rem; border-radius:8px 8px 2px 8px; }
        .brand-name { font:700 18px 'Space Grotesk'; letter-spacing:-.5px; }
        .brand-sub { color:#a9a69c; font-size:10px; letter-spacing:1.2px; text-transform:uppercase; margin-top:9px; }
        .eyebrow { color:var(--orange-dark); font-size:.75rem; font-weight:700; letter-spacing:1.8px; text-transform:uppercase; }
        .hero-copy { padding:1.5rem 0 2rem; }
        .action-card { background:var(--panel); border:2px solid var(--line); border-radius:14px; padding:1.8rem; height:100%; transition:all .2s ease; box-shadow:0 6px 18px rgba(0,0,0,.04); }
        .action-card:hover { border-color:var(--orange); transform:translateY(-2px); }
        .action-card h2 { margin:.4rem 0 .6rem; color:#17202a !important; font-size:1.6rem; }
        .action-card p { font-size:1.02rem; line-height:1.55; margin-bottom:1.4rem; color:#4a4740; }
        .panel { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:1.25rem; box-shadow:0 8px 22px rgba(70,58,40,.05); }
        .metric-panel { min-height:110px; border-top:4px solid var(--orange); position:relative; overflow:hidden; }
        .metric-label { text-transform:uppercase; letter-spacing:1px; font-size:.67rem; color:var(--secondary); font-weight:700; }
        .metric-value { color:var(--ink); font:700 1.9rem 'Space Grotesk'; margin-top:.4rem; }
        .uploaded-photo { border-radius:12px; border:1px solid var(--line); background:#e8e0d4; padding:.6rem; }
        .page-title { padding:1.8rem 0 1.4rem; } .page-title h1 { font-size:3.2rem; margin-bottom:.5rem; }
        .footer-note { text-align:center; color:#777269; font-size:.75rem; padding:3rem 0 1rem; }
        .analysis-heading h2, .analysis-section h2 { color:#17202a !important; margin:1.8rem 0 1rem; }
        .analysis-metric { background:var(--panel); border:1px solid var(--line); border-top:4px solid var(--orange); border-radius:10px; padding:1rem; min-height:85px; }
        .analysis-metric span { display:block; color:#333; font-size:.68rem; font-weight:700; letter-spacing:.5px; text-transform:uppercase; }
        .analysis-metric strong { display:block; color:#17202a; font:700 1.45rem 'Space Grotesk'; margin-top:.35rem; }
        .placement-card { background:var(--panel); border:1px solid var(--line); border-left:5px solid var(--orange); border-radius:8px; padding:1rem 1.2rem; margin:.7rem 0; }
        .placement-card h3 { font-size:1.15rem; margin:0 0 .3rem; color:#17202a !important; }
        .placement-card p { font-size:.92rem; margin:.2rem 0; color:#333; }
        .empty-state { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:2rem; min-height:240px; }
        .auth-visual { background:#2d2c27 center/cover no-repeat; border-radius:14px; min-height:480px; height:100%; padding:2.8rem; color:#ffffff !important; position:relative; overflow:hidden; }
        .auth-visual:before { content:''; position:absolute; inset:0; background:linear-gradient(180deg, rgba(18,17,14,0.62) 0%, rgba(18,17,14,0.85) 100%); z-index:1; }
        .auth-visual > * { position:relative; z-index:2; }
        .auth-visual h1 { color:#ffffff !important; font-size:3.4rem; font-weight:700; margin:1.8rem 0 .6rem; text-shadow:0 2px 10px rgba(0,0,0,0.5); }
        .auth-visual p { color:#f5f0eb !important; font-size:1.15rem; line-height:1.65; max-width:400px; text-shadow:0 1px 5px rgba(0,0,0,0.5); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_session() -> None:
    defaults = {
        "authenticated": False,
        "auth_mode": "login",
        "page": "Home",
        "shelf_image": None,
        "shelf_image_name": "",
        "shelf_image_mime": "",
        "shelf_goal": "Overall Shelf Review",
        "shelf_analysis": None,
        "analysis_source": "",
        "shelf_analyses": [],
        "empty_shelf_image": None,
        "empty_shelf_image_name": "",
        "empty_shelf_image_mime": "",
        "empty_shelf_levels": 4,
        "empty_shelf_categories": ["Biscuits", "Chocolates", "Chips", "Cookies", "Drinks"],
        "empty_shelf_plan": None,
        "empty_plan_source": "",
        "analysis_error_message": "",
        "analysis_retry_available": False,
        "analysis_retry_label": "Try Analysis Again",
        "language": "en",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def analysis_record_to_model(record: dict):
    analysis = record["analysis"]
    if hasattr(analysis, "model_dump"):
        return analysis
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


def render_auth() -> None:
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        login_image = html.escape(image_source("login"), quote=True)
        st.markdown(
            f"""
            <div class="auth-visual" style="background-image:url('{login_image}');">
                <div>
                    <div style="display:inline-flex; width:40px; height:40px; background:#e66f32; border-radius:8px; align-items:center; justify-content:center; font-weight:700; color:#fff; font-size:18px;">SS</div>
                    <h1>ShelfSight</h1>
                    <p>AI-powered retail merchandising intelligence for smart shopkeepers.</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        with st.container(border=True):
            if st.session_state.auth_mode == "login":
                st.markdown('<div class="eyebrow">STORE TEAM ACCESS</div><h2 style="margin:.3rem 0 1rem; color:#17202a !important;">Welcome Back</h2><p style="margin-bottom:1.5rem">Sign in to manage your store shelves.</p>', unsafe_allow_html=True)
                with st.form("login_form"):
                    st.text_input("Email / Store ID", value="manager@store.com", placeholder="you@store.com")
                    st.text_input("Password", type="password", value="••••••••", placeholder="Enter password")
                    submitted = st.form_submit_button("Sign In →", type="primary", use_container_width=True)
                    if submitted:
                        st.session_state.authenticated = True
                        st.session_state.page = "Home"
                        st.rerun()
                st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
                if st.button("Need an account? Create one", use_container_width=True, key="goto_signup"):
                    st.session_state.auth_mode = "signup"
                    st.rerun()
            else:
                st.markdown('<div class="eyebrow">NEW STORE WORKSPACE</div><h2 style="margin:.3rem 0 1rem; color:#17202a !important;">Create Account</h2><p style="margin-bottom:1.5rem">Get started with ShelfSight for your shop.</p>', unsafe_allow_html=True)
                with st.form("signup_form"):
                    st.text_input("Full Name", placeholder="Store Manager")
                    st.text_input("Store Name", placeholder="Northstar Retail")
                    st.text_input("Email", placeholder="you@store.com")
                    st.text_input("Password", type="password", placeholder="Choose password")
                    submitted = st.form_submit_button("Create Account →", type="primary", use_container_width=True)
                    if submitted:
                        st.session_state.authenticated = True
                        st.session_state.page = "Home"
                        st.rerun()
                st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
                if st.button("Already have an account? Sign in", use_container_width=True, key="goto_login"):
                    st.session_state.auth_mode = "login"
                    st.rerun()


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown('<div class="brand-lockup"><span class="brand-mark">SS</span><span class="brand-name">ShelfSight</span><div class="brand-sub">Retail Merchandising AI</div></div>', unsafe_allow_html=True)
        current = st.session_state.page
        for icon, label in NAV_GROUPS[""]:
            page = PAGE_BY_LABEL[label]
            display = {"Home": t("home"), "Check My Shelf": t("check"), "Plan New Shelf": t("plan"), "Store Evolution": t("progress")}.get(page, label)
            if st.button(f"{icon}  {display}", key=f"nav_{label}", type="primary" if page == current else "secondary", use_container_width=True):
                st.session_state.page = page
                st.rerun()
        st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
        st.caption(f"{t('language')}: {st.session_state.get('language','en').upper()}")
        if st.button("Sign out", key="sign_out_btn", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.auth_mode = "login"
            st.rerun()
    return current


def render_home() -> None:
    # Direct Language selector at top of Home page
    st.markdown(f"<div style='display:flex;justify-content:flex-end;align-items:center;gap:.8rem;margin-bottom:1.2rem'><span style='font-weight:700'>{html.escape(t('language'))}:</span></div>", unsafe_allow_html=True)
    lang_col1, lang_col2 = st.columns([3, 1])
    with lang_col2:
        language = st.selectbox(
            t("language"),
            list(LANGUAGES.keys()),
            index=list(LANGUAGES.values()).index(st.session_state.get("language", "en")),
            label_visibility="collapsed",
            key="home_language_select",
        )
        selected_code = LANGUAGES[language]
        if selected_code != st.session_state.get("language", "en"):
            st.session_state.language = selected_code
            st.rerun()

    st.markdown(f"<div class='hero-copy'><div class='eyebrow'>ShelfSight AI</div><h1>{html.escape(t('hero_title'))}</h1><p>{html.escape(t('hero_body'))}</p></div>", unsafe_allow_html=True)

    # Two Large Primary Action Cards
    col_left, col_right = st.columns(2, gap="large")
    with col_left:
        st.markdown(
            f"""
            <div class="action-card">
                <div class="eyebrow">OPTION 1</div>
                <h2>{html.escape(t('check'))}</h2>
                <p>{html.escape(t('check_desc'))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(t("check_btn"), type="primary", use_container_width=True, key="home_check_btn"):
            st.session_state.page = "Check My Shelf"
            st.rerun()

    with col_right:
        st.markdown(
            f"""
            <div class="action-card">
                <div class="eyebrow">OPTION 2</div>
                <h2>{html.escape(t('plan'))}</h2>
                <p>{html.escape(t('plan_desc'))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(t("plan_btn"), type="primary", use_container_width=True, key="home_plan_btn"):
            st.session_state.page = "Plan New Shelf"
            st.rerun()

    # Secondary Store Progress Link
    st.markdown("<div style='margin-top:2.5rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        p_col1, p_col2 = st.columns([2.5, 1], gap="medium")
        with p_col1:
            st.markdown(f"### {html.escape(t('progress'))}")
            st.write(t("progress_desc"))
        with p_col2:
            st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
            if st.button(t("progress_btn"), use_container_width=True, key="home_progress_btn"):
                st.session_state.page = "Store Evolution"
                st.rerun()


def render_inspect_shelf() -> None:
    st.markdown(f'<div class="page-title"><div class="eyebrow">Shelf Analysis</div><h1>{html.escape(t("check"))}</h1><p>{html.escape(t("check_desc"))}</p></div>', unsafe_allow_html=True)

    left, right = st.columns([.88, 1.12], gap="large")
    with left:
        st.markdown(f'<div class="eyebrow">Step 1</div><h2>{html.escape(t("upload_check"))}</h2><p>Upload a clear photo of your shelf showing visible products.</p>', unsafe_allow_html=True)
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
            st.success(f"Shelf photo ready: {uploaded.name}")

        st.markdown(f'<div class="eyebrow" style="margin-top:1.8rem">Step 2</div><h2>{html.escape(t("goal"))}</h2>', unsafe_allow_html=True)
        goal = st.radio("Goal", ["Overall Shelf Review", "Improve Product Visibility", "Reduce Empty Space", "Improve Organization", "Highlight Promotional Products"], label_visibility="collapsed")
        st.session_state.shelf_goal = goal
        section = st.selectbox("Shelf Section", ["Beverages", "Snacks", "Grocery", "Personal Care", "Premium Display", "Other"], key="check_section")

        st.markdown('<div class="eyebrow" style="margin-top:1.4rem">Step 3</div>', unsafe_allow_html=True)
        analyze_requested = st.button(t("analyze"), type="primary", use_container_width=True)

        if analyze_requested:
            if st.session_state.shelf_image is None:
                st.warning("Please upload a shelf photo first.")
            else:
                with st.status("Analyzing shelf image...", expanded=False) as status:
                    try:
                        analysis, source = analyze_shelf(
                            st.session_state.shelf_image,
                            st.session_state.shelf_image_mime,
                            goal,
                            status_callback=lambda msg: status.update(label=msg),
                        )
                        st.session_state.shelf_analysis = analysis
                        st.session_state.analysis_source = source
                        save_analysis_record(analysis, st.session_state.shelf_image, st.session_state.shelf_image_name, st.session_state.shelf_image_mime, goal, section)
                        status.update(label="Analysis complete.", state="complete")
                    except AnalysisError as exc:
                        st.session_state.shelf_analysis = None
                        st.error(str(exc))
                        status.update(label="Analysis unavailable.", state="error")

    with right:
        if st.session_state.shelf_image:
            st.markdown('<div class="eyebrow">Your Uploaded Photo</div>', unsafe_allow_html=True)
            st.image(st.session_state.shelf_image, caption=st.session_state.shelf_image_name, use_container_width=True)
        else:
            placeholder = html.escape(image_source("shelf"), quote=True)
            st.markdown(f'<div class="upload-placeholder" style="background-image:url(\'{placeholder}\')"><div><strong>Your shelf photo will appear here</strong><span>Upload a clear image of your shelf with products.</span></div></div>', unsafe_allow_html=True)

    # RESULTS SECTION
    if st.session_state.shelf_analysis is not None:
        analysis: ShelfAnalysis = st.session_state.shelf_analysis
        st.markdown('<div style="margin-top:2.5rem"></div>', unsafe_allow_html=True)

        if st.session_state.analysis_source == "demo":
            st.info("Demo mode: Sample analysis shown because Gemini API is temporarily busy.")

        # 1. PRIMARY RESULT: VISUAL OVERLAY FIRST
        st.markdown(f"<div class='analysis-section'><h2>{html.escape(t('action_guide'))}</h2><p>Look at the highlighted shelf areas below. Yellow/Red highlights show specific areas needing attention. Unmarked areas can stay as they are.</p></div>", unsafe_allow_html=True)
        render_current_vs_recommended(st.session_state.shelf_image, analysis)

        # 2. WRITTEN FINDINGS & RECOMMENDATIONS
        st.markdown(f"<div class='analysis-section'><h2>{html.escape(t('found'))}</h2></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='analysis-summary'>{html.escape(analysis.summary)}</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        for issue in analysis.detected_issues:
            with st.container(border=True):
                st.markdown(f"**{html.escape(issue.severity)} Priority — {html.escape(issue.issue)}**")
                st.write(f"**Why it matters:** {issue.evidence}")
                st.write(f"**What to do:** {issue.recommendation}")

        # 3. NUMERICAL SCORES AFTER VISUAL RESULT
        st.markdown(f"<div class='analysis-section'><h2>{html.escape(t('scores'))}</h2></div>", unsafe_allow_html=True)
        metric_values = score_values(analysis)
        cols = st.columns(len(metric_values), gap="small")
        for col, (label, val) in zip(cols, metric_values.items()):
            with col:
                st.markdown(f'<div class="analysis-metric"><span>{html.escape(label)}</span><strong>{val} / 100</strong></div>', unsafe_allow_html=True)


def render_plan_new_shelf() -> None:
    st.markdown(f'<div class="page-title"><div class="eyebrow">Empty Shelf Planning</div><h1>{html.escape(t("plan"))}</h1><p>{html.escape(t("plan_desc"))}</p></div>', unsafe_allow_html=True)

    left, right = st.columns([.88, 1.12], gap="large")
    with left:
        st.markdown(f'<div class="eyebrow">Step 1</div><h2>{html.escape(t("upload_plan"))}</h2><p>Upload a photo of your empty shelf or display fixture.</p>', unsafe_allow_html=True)
        uploaded = st.file_uploader("Choose an empty shelf photo", type=["jpg", "jpeg", "png", "webp"], key="empty_uploader", label_visibility="collapsed")
        if uploaded is not None:
            uploaded_bytes = uploaded.getvalue()
            if uploaded_bytes != st.session_state.empty_shelf_image:
                st.session_state.empty_shelf_image = uploaded_bytes
                st.session_state.empty_shelf_image_name = uploaded.name
                st.session_state.empty_shelf_image_mime = uploaded.type or "image/jpeg"
                st.session_state.empty_shelf_plan = None
            st.success(f"Empty shelf photo ready: {uploaded.name}")

        st.markdown('<div class="eyebrow" style="margin-top:1.8rem">Step 2</div><h2>Number of Shelf Levels</h2>', unsafe_allow_html=True)
        levels = st.slider("How many shelf levels do you have?", min_value=2, max_value=5, value=st.session_state.empty_shelf_levels, key="shelf_levels_slider")
        st.session_state.empty_shelf_levels = levels

        st.markdown('<div class="eyebrow" style="margin-top:1.8rem">Step 3</div><h2>Product Categories to Stock</h2>', unsafe_allow_html=True)
        available_cats = ["Biscuits", "Chocolates", "Chips", "Cookies", "Snacks", "Drinks", "Other"]
        selected_cats = st.multiselect(
            "Select product categories for this shelf:",
            available_cats,
            default=st.session_state.empty_shelf_categories,
            key="categories_multiselect",
        )
        st.session_state.empty_shelf_categories = selected_cats

        st.markdown('<div class="eyebrow" style="margin-top:1.4rem">Step 4</div>', unsafe_allow_html=True)
        plan_requested = st.button(t("generate_plan"), type="primary", use_container_width=True, key="generate_empty_plan_btn")

        if plan_requested:
            if st.session_state.empty_shelf_image is None:
                st.warning("Please upload an empty shelf photo first.")
            elif not selected_cats:
                st.warning("Please select at least one product category.")
            else:
                with st.status("Creating placement plan...", expanded=False) as status:
                    try:
                        plan, source = analyze_empty_shelf(
                            st.session_state.empty_shelf_image,
                            st.session_state.empty_shelf_image_mime,
                            levels,
                            selected_cats,
                            status_callback=lambda msg: status.update(label=msg),
                        )
                        st.session_state.empty_shelf_plan = plan
                        st.session_state.empty_plan_source = source
                        status.update(label="Placement plan ready.", state="complete")
                    except Exception as exc:
                        st.session_state.empty_shelf_plan = None
                        st.error(f"Could not generate plan: {str(exc)}")
                        status.update(label="Planning unavailable.", state="error")

    with right:
        if st.session_state.empty_shelf_image:
            st.markdown('<div class="eyebrow">Uploaded Empty Shelf</div>', unsafe_allow_html=True)
            st.image(st.session_state.empty_shelf_image, caption=st.session_state.empty_shelf_image_name, use_container_width=True)
        else:
            placeholder = html.escape(image_source("shelf"), quote=True)
            st.markdown(f'<div class="upload-placeholder" style="background-image:url(\'{placeholder}\')"><div><strong>Empty shelf photo will appear here</strong><span>Start with a photo of an empty shelf or rack.</span></div></div>', unsafe_allow_html=True)

    # PLAN OUTPUT SECTION
    if st.session_state.empty_shelf_plan is not None:
        plan: EmptyShelfPlan = st.session_state.empty_shelf_plan
        st.markdown('<div style="margin-top:2.5rem"></div>', unsafe_allow_html=True)
        st.markdown(f"<div class='analysis-section'><h2>{html.escape(t('where_put'))}</h2><p>Follow the visual placement regions overlaid on your empty shelf photo below.</p></div>", unsafe_allow_html=True)

        plan_img = create_empty_shelf_plan_image(st.session_state.empty_shelf_image, plan)
        if plan_img:
            st.image(plan_img, caption="Visual placement guide overlaid on your real empty shelf photo", use_container_width=True)

        st.caption("Visual placement guide based on merchandising principles. Products are not physically placed in the image.")

        st.markdown("<div class='analysis-section'><h2>Category Placement Instructions</h2></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='analysis-summary'>{html.escape(plan.summary)}</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        for p in plan.placements:
            st.markdown(
                f"""
                <div class="placement-card">
                    <h3>{html.escape(p.category)} &rarr; {html.escape(p.recommended_zone.upper())} LEVEL</h3>
                    <p><strong>Why:</strong> {html.escape(p.reason)}</p>
                    <p><strong>Tip:</strong> {html.escape(p.tip)}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_store_evolution() -> None:
    records = st.session_state.shelf_analyses
    st.markdown(f"<div class='page-title'><div class='eyebrow'>ShelfSight / {html.escape(t('progress'))}</div><h1>{html.escape(t('progress'))}</h1><p>Compare real shelf photos over time to see improvement.</p></div>", unsafe_allow_html=True)

    if not records:
        st.markdown('<div class="empty-state"><h2>No shelf history saved yet.</h2><p>Check a shelf to start tracking store progress.</p></div>', unsafe_allow_html=True)
        if st.button("Check My Shelf →", type="primary", key="check_from_progress"):
            st.session_state.page = "Check My Shelf"
            st.rerun()
        return

    if len(records) == 1:
        latest = analysis_record_to_model(records[-1])
        st.markdown("<div class='panel'><h2>First shelf scan recorded.</h2><p>Take another photo of the shelf after making improvements to see before-and-after comparisons.</p></div>", unsafe_allow_html=True)
        st.image(records[-1]["image"], caption="Latest shelf photo", use_container_width=True)
        st.metric("Shelf Health Score", f"{latest.overall_score} / 100")
        return

    previous_record, latest_record = records[-2], records[-1]
    previous = analysis_record_to_model(previous_record)
    latest = analysis_record_to_model(latest_record)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("**BEFORE PHOTO**")
        st.image(previous_record["image"], use_container_width=True)
        st.caption(f"Scanned: {previous_record['timestamp'].replace('T', ' ')}")
    with col2:
        st.markdown("**AFTER PHOTO**")
        st.image(latest_record["image"], use_container_width=True)
        st.caption(f"Scanned: {latest_record['timestamp'].replace('T', ' ')}")

    st.markdown("<div class='analysis-section'><h2>Supporting Score Changes</h2></div>", unsafe_allow_html=True)
    m_cols = st.columns(3)
    with m_cols[0]: st.metric("Earlier Score", f"{previous.overall_score} / 100")
    with m_cols[1]: st.metric("Latest Score", f"{latest.overall_score} / 100")
    with m_cols[2]: st.metric("Score Delta", f"{latest.overall_score - previous.overall_score:+d}")


def main() -> None:
    init_session()
    inject_styles()
    if not st.session_state.authenticated:
        render_auth()
        return
    page = render_sidebar()
    if page == "Home":
        render_home()
    elif page == "Check My Shelf":
        render_inspect_shelf()
    elif page == "Plan New Shelf":
        render_plan_new_shelf()
    elif page == "Store Evolution":
        render_store_evolution()
    else:
        st.session_state.page = "Home"
        render_home()
    st.markdown('<div class="footer-note">ShelfSight / Retail Merchandising Intelligence</div>', unsafe_allow_html=True)
    reset_main_scroll()


if __name__ == "__main__":
    main()