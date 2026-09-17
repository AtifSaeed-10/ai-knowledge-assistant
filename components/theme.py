"""
Theme system for DocuSage.

Single source of truth for color tokens, shadows, and the global CSS
that reskins Streamlit's default chrome into the premium look. Dark
and light are the same CSS with different variable values, so toggling
never involves loading a second stylesheet.
"""

import streamlit as st
from utils.state import get_state

TOKENS = {
    "dark": {
        "bg-app": "#0C100D",
        "bg-surface": "#141A16",
        "bg-card": "#1C241F",
        "bg-card-hover": "#232E27",
        "accent-olive": "#87AB72",
        "accent-olive-glow": "rgba(135, 171, 114, 0.25)",
        "accent-sage-subtle": "rgba(163, 177, 138, 0.18)",
        "text-main": "#F1F4F0",
        "text-muted": "#8C9B8F",
        "border-subtle": "#27332B",
        "shadow-sm": "0 1px 3px rgba(0, 0, 0, 0.4)",
        "shadow-md": "0 4px 14px rgba(0, 0, 0, 0.5), 0 1px 3px rgba(12, 16, 13, 0.3)",
        "shadow-lg": "0 12px 30px rgba(0, 0, 0, 0.6), 0 2px 8px rgba(135, 171, 114, 0.05)",
    },
    "light": {
        "bg-app": "#F6F7F4",
        "bg-surface": "#EBECE7",
        "bg-card": "#FFFFFF",
        "bg-card-hover": "#FAFBF9",
        "accent-olive": "#4A5D3E",
        "accent-olive-glow": "rgba(74, 93, 62, 0.12)",
        "accent-sage-subtle": "#E4EBDC",
        "text-main": "#1C231B",
        "text-muted": "#637062",
        "border-subtle": "#D8DDD5",
        "shadow-sm": "0 1px 3px rgba(28, 35, 27, 0.06)",
        "shadow-md": "0 4px 14px rgba(28, 35, 27, 0.08), 0 1px 2px rgba(28, 35, 27, 0.04)",
        "shadow-lg": "0 16px 32px rgba(28, 35, 27, 0.1), 0 4px 8px rgba(28, 35, 27, 0.04)",
    },
}


def _css_vars(theme):
    t = TOKENS[theme]
    lines = [f"    --{key}: {value};" for key, value in t.items()]
    lines.append(f"    --shadow-glow: 0 0 20px {t['accent-olive-glow']};" if theme == "dark"
                  else f"    --shadow-glow: 0 0 16px {t['accent-olive-glow']};")
    return "\n".join(lines)


def inject_theme():
    theme = get_state("theme_preference") or "dark"
    css_vars = _css_vars(theme)

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

        :root {{
{css_vars}
        }}

        html, body, [class*="css"] {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        }}

        /* ---------- App canvas ---------- */
        .stApp {{
            background-color: var(--bg-app);
            color: var(--text-main);
        }}

        /* Hide Streamlit's default chrome so the app doesn't read as a demo */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header[data-testid="stHeader"] {{
            background-color: transparent;
        }}
        div[data-testid="stDecoration"] {{display: none;}}
        div[data-testid="stStatusWidget"] {{visibility: hidden;}}

        /* ---------- Sidebar ---------- */
        section[data-testid="stSidebar"] {{
            background-color: var(--bg-surface);
            border-right: 1px solid var(--border-subtle);
        }}
        section[data-testid="stSidebar"] > div {{
            padding-top: 1.25rem;
        }}

        /* ---------- Typography ---------- */
        h1, h2, h3, h4, h5, h6 {{
            color: var(--text-main);
            font-weight: 700;
            letter-spacing: -0.02em;
        }}
        p, span, label, li {{
            color: var(--text-main);
        }}
        .ds-muted {{
            color: var(--text-muted) !important;
        }}

        /* ---------- Buttons ---------- */
        .stButton > button {{
            background-color: var(--bg-card);
            color: var(--text-main);
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 0.55rem 1rem;
            font-weight: 600;
            font-size: 0.9rem;
            transition: all 0.15s ease;
            box-shadow: var(--shadow-sm);
        }}
        .stButton > button:hover {{
            background-color: var(--bg-card-hover);
            border-color: var(--accent-olive);
            color: var(--accent-olive);
        }}
        .stButton > button:focus:not(:active) {{
            border-color: var(--accent-olive);
            box-shadow: var(--shadow-glow);
        }}

        /* Primary CTA — target via the help kwarg trick isn't needed;
           we mark primary buttons with type="primary" from Streamlit. */
        .stButton > button[kind="primary"] {{
            background-color: var(--accent-olive);
            color: {"#0C100D" if theme == "dark" else "#FFFFFF"};
            border: 1px solid var(--accent-olive);
        }}
        .stButton > button[kind="primary"]:hover {{
            box-shadow: var(--shadow-glow);
            opacity: 0.92;
            color: {"#0C100D" if theme == "dark" else "#FFFFFF"};
        }}

        /* ---------- Inputs ---------- */
        .stTextInput input, .stTextArea textarea, .stChatInput textarea {{
            background-color: var(--bg-card);
            color: var(--text-main);
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
        }}
        .stTextInput input:focus, .stTextArea textarea:focus, .stChatInput textarea:focus {{
            border-color: var(--accent-olive);
            box-shadow: var(--shadow-glow);
        }}
        div[data-testid="stChatInput"] {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: 14px;
            box-shadow: var(--shadow-sm);
        }}
        div[data-testid="stFileUploader"] section {{
            background-color: var(--bg-card);
            border: 1.5px dashed var(--border-subtle);
            border-radius: 14px;
        }}
        div[data-testid="stFileUploader"] section:hover {{
            border-color: var(--accent-olive);
        }}

        /* ---------- Cards (generic building block) ---------- */
        .ds-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: 14px;
            padding: 1rem 1.1rem;
            box-shadow: var(--shadow-sm);
            transition: background-color 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
        }}
        .ds-card:hover {{
            background-color: var(--bg-card-hover);
        }}
        .ds-card-elevated {{
            box-shadow: var(--shadow-lg);
        }}

        /* ---------- Dividers ---------- */
        hr, div[data-testid="stDivider"] {{
            border-color: var(--border-subtle) !important;
        }}

        /* ---------- Scrollbar ---------- */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{
            background: var(--border-subtle);
            border-radius: 8px;
        }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--accent-olive); }}

        /* ---------- Misc Streamlit widget restyling ---------- */
        .stRadio label, .stCheckbox label {{
            color: var(--text-main) !important;
        }}
        div[data-baseweb="select"] > div {{
            background-color: var(--bg-card);
            border-color: var(--border-subtle);
        }}
        .stAlert {{
            border-radius: 12px;
            border: 1px solid var(--border-subtle);
        }}

        /* ---------- Layout helpers ---------- */
        .block-container {{
            padding-top: 1.5rem;
            max-width: 1400px;
        }}

        @media (max-width: 768px) {{
            .block-container {{
                padding-left: 0.75rem;
                padding-right: 0.75rem;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def token(name):
    """Fetch a raw token value for the active theme (for building HTML snippets in components)."""
    theme = get_state("theme_preference") or "dark"
    return TOKENS[theme].get(name)
