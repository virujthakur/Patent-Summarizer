import streamlit as st

from db import get_user_theme_preference, set_user_theme_preference

VALID_THEMES = {"light", "dark"}
DEFAULT_THEME = "light"


def _sanitize_theme(theme_mode):
    if theme_mode in VALID_THEMES:
        return theme_mode
    return DEFAULT_THEME


def get_active_theme(current_user=None):
    if "theme_mode" in st.session_state:
        return _sanitize_theme(st.session_state["theme_mode"])

    theme_mode = DEFAULT_THEME
    if current_user and current_user.get("user_id"):
        stored = get_user_theme_preference(current_user["user_id"])
        if stored in VALID_THEMES:
            theme_mode = stored

    st.session_state["theme_mode"] = theme_mode
    return theme_mode


def persist_theme(theme_mode, current_user=None):
    theme_mode = _sanitize_theme(theme_mode)
    st.session_state["theme_mode"] = theme_mode

    if current_user and current_user.get("user_id"):
        set_user_theme_preference(current_user["user_id"], theme_mode)



def render_theme_toggle(current_user=None, key="theme_toggle"):
    active_theme = get_active_theme(current_user)
    dark_enabled = st.toggle("Dark mode", value=(active_theme == "dark"), key=key)
    desired = "dark" if dark_enabled else "light"
    if desired != active_theme:
        persist_theme(desired, current_user)
        st.rerun()

    return desired


def inject_theme_css(theme_mode):
    theme_mode = _sanitize_theme(theme_mode)

    if theme_mode == "dark":
        palette = {
            "paper": "#0d141f",
            "paper_soft": "#111b2a",
            "ink": "#e5edf7",
            "muted": "#9db0c8",
            "coral": "#f37b65",
            "teal": "#5fd6e3",
            "card_border": "rgba(157, 176, 200, 0.28)",
        "form_border": "rgba(157, 176, 200, 0.52)",
            "card_bg": "rgba(17, 27, 42, 0.78)",
            "shadow": "rgba(0, 0, 0, 0.3)",
        }
    else:
        palette = {
            "paper": "#f8f6ef",
            "paper_soft": "#edf6f8",
            "ink": "#0e1726",
            "muted": "#5f697a",
            "coral": "#f15b42",
            "teal": "#0b6e79",
            "card_border": "rgba(14, 23, 38, 0.12)",
            "form_border": "rgba(14, 23, 38, 0.24)",
            "card_bg": "rgba(255, 255, 255, 0.7)",
            "shadow": "rgba(14, 23, 38, 0.08)",
        }

    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500&display=swap');

:root {{
  --paper: {palette['paper']};
  --paper-soft: {palette['paper_soft']};
  --ink: {palette['ink']};
  --muted: {palette['muted']};
  --coral: {palette['coral']};
  --teal: {palette['teal']};
  --card-border: {palette['card_border']};
  --form-border: {palette['form_border']};
  --card-bg: {palette['card_bg']};
  --soft-shadow: {palette['shadow']};
}}

.stApp {{
  font-family: 'IBM Plex Sans', sans-serif;
  background:
    radial-gradient(circle at 8% 12%, color-mix(in srgb, var(--coral) 26%, transparent), transparent 30%),
    radial-gradient(circle at 85% 10%, color-mix(in srgb, var(--teal) 23%, transparent), transparent 35%),
    linear-gradient(150deg, var(--paper) 20%, var(--paper-soft) 100%);
  color: var(--ink);
}}

[data-testid="stSidebar"],
[data-testid="collapsedControl"],
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {{
  display: none !important;
}}

#MainMenu {{
  visibility: hidden;
}}

h1, h2, h3 {{
  font-family: 'Space Grotesk', sans-serif;
  letter-spacing: -0.02em;
  color: var(--ink);
}}

p, span, label, div {{
  color: var(--ink);
}}

.auth-subtitle, .auth-note, .stCaption {{
  color: var(--muted) !important;
}}

div[data-testid="stVerticalBlockBorderWrapper"],
.card {{
  background: var(--card-bg);
  border: 1.5px solid var(--form-border);
  border-radius: 16px;
  box-shadow: 0 8px 22px var(--soft-shadow);
}}

.stForm,
div[data-testid="stForm"] {{
  border: 1px solid var(--form-border) !important;
  border-radius: 14px !important;
  background: color-mix(in srgb, var(--card-bg) 92%, transparent) !important;
}}

div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div,
div[data-testid="stFileUploader"] > div,
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] > div,
div[data-testid="stMultiSelect"] > div {{
  border-color: var(--form-border) !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] div,
div[data-testid="stSelectbox"] [data-baseweb="select"] span,
div[data-testid="stSelectbox"] [data-baseweb="select"] input,
div[data-testid="stSelectbox"] [data-baseweb="select"] div[role="combobox"],
div[data-testid="stSelectbox"] [data-baseweb="select"] div[role="option"],
div[data-testid="stSelectbox"] [data-baseweb="select"] div[aria-selected="true"] {{
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
div[data-testid="stSelectbox"] [data-baseweb="select"] > div > div,
div[data-testid="stSelectbox"] [data-baseweb="select"] > div > div > div {{
  background: var(--paper-soft) !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  border-color: var(--form-border) !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] input::placeholder {{
  color: color-mix(in srgb, var(--ink) 72%, transparent) !important;
  -webkit-text-fill-color: color-mix(in srgb, var(--ink) 72%, transparent) !important;
  opacity: 1 !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] svg {{
  fill: var(--ink) !important;
  color: var(--ink) !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] div[data-baseweb="popover"] {{
  background: var(--card-bg) !important;
  border: 1px solid var(--form-border) !important;
  box-shadow: 0 10px 28px var(--soft-shadow) !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] div[data-baseweb="popover"] * {{
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}}

div[data-baseweb="popover"] {{
  background: var(--card-bg) !important;
  border: 1px solid var(--form-border) !important;
  box-shadow: 0 10px 28px var(--soft-shadow) !important;
}}

div[data-baseweb="popover"] * {{
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] div[role="listbox"],
div[data-testid="stSelectbox"] [data-baseweb="select"] ul {{
  background: var(--card-bg) !important;
  color: var(--ink) !important;
}}

div[data-baseweb="popover"] div[role="listbox"],
div[data-baseweb="popover"] ul {{
  background: var(--card-bg) !important;
  color: var(--ink) !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] div[role="option"],
div[data-testid="stSelectbox"] [data-baseweb="select"] li {{
  color: var(--ink) !important;
  background: transparent !important;
}}

div[data-baseweb="popover"] div[role="option"],
div[data-baseweb="popover"] li {{
  color: var(--ink) !important;
  background: transparent !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] div[role="option"][aria-selected="true"],
div[data-testid="stSelectbox"] [data-baseweb="select"] li[aria-selected="true"] {{
  background: color-mix(in srgb, var(--coral) 18%, transparent) !important;
  color: var(--ink) !important;
}}

div[data-baseweb="popover"] div[role="option"][aria-selected="true"],
div[data-baseweb="popover"] li[aria-selected="true"] {{
  background: color-mix(in srgb, var(--coral) 18%, transparent) !important;
  color: var(--ink) !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] div[role="option"]:hover,
div[data-testid="stSelectbox"] [data-baseweb="select"] li:hover {{
  background: color-mix(in srgb, var(--paper-soft) 72%, transparent) !important;
}}

div[data-baseweb="popover"] div[role="option"]:hover,
div[data-baseweb="popover"] li:hover {{
  background: color-mix(in srgb, var(--paper-soft) 72%, transparent) !important;
}}

div[data-testid="stFileUploader"] button,
div[data-testid="stFileUploader"] button span,
div[data-testid="stFileUploader"] button p,
div[data-testid="stFileUploader"] button div,
div[data-testid="stFileUploaderDropzone"] button,
div[data-testid="stFileUploaderDropzone"] button span,
div[data-testid="stFileUploaderDropzone"] button p,
div[data-testid="stFileUploaderDropzone"] button div {{
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  background: color-mix(in srgb, var(--paper-soft) 78%, transparent) !important;
  border: 1px solid var(--card-border) !important;
}}

div[data-testid="stFileUploader"] button:hover,
div[data-testid="stFileUploaderDropzone"] button:hover {{
  background: color-mix(in srgb, var(--paper-soft) 88%, white) !important;
  border-color: var(--form-border) !important;
}}

div[data-testid="stButton"] button,
div[data-testid="stDownloadButton"] button,
div[data-testid="stFormSubmitButton"] button,
button[data-testid^="baseButton-"] {{
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  border: 1px solid var(--card-border) !important;
  background: color-mix(in srgb, var(--paper-soft) 78%, transparent) !important;
}}

div[data-testid="stButton"] button[kind="primary"],
div[data-testid="stFormSubmitButton"] button[kind="primary"],
button[data-testid^="baseButton-"][kind="primary"] {{
  background: var(--coral) !important;
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
  border-color: color-mix(in srgb, var(--coral) 70%, black) !important;
}}

div[data-testid="stButton"] button:disabled,
div[data-testid="stDownloadButton"] button:disabled,
div[data-testid="stFormSubmitButton"] button:disabled,
button[data-testid^="baseButton-"]:disabled {{
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  background: color-mix(in srgb, var(--paper-soft) 60%, transparent) !important;
  border-color: var(--card-border) !important;
  opacity: 0.75;
}}

div[data-testid="stButton"] button > div,
div[data-testid="stDownloadButton"] button > div,
div[data-testid="stFormSubmitButton"] button > div,
div[data-testid="stButton"] button p,
div[data-testid="stDownloadButton"] button p,
div[data-testid="stFormSubmitButton"] button p,
div[data-testid="stButton"] button span,
div[data-testid="stDownloadButton"] button span,
div[data-testid="stFormSubmitButton"] button span {{
  color: inherit !important;
  -webkit-text-fill-color: inherit !important;
}}

.top-nav-label {{
  font-size: 0.9rem;
  font-weight: 700;
  margin-bottom: 0.35rem;
}}

@media (max-width: 980px) {{
  .top-nav-label {{
    margin-top: 0.4rem;
  }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
