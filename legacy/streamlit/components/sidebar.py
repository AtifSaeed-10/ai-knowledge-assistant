"""
Left sidebar: logo, upload, document library, settings entry point.
"""

import streamlit as st
from components.upload import render_upload_widget
from components.documents import render_document_library, refresh_documents, DOCUMENTS_CSS
from components.theme import token
from utils.state import get_state, set_state

LOGO_ICON = """
<g transform="translate(2, 2)">
    <path d="M 26 4 H 8 C 4.686 4 2 6.686 2 10 V 48 C 2 51.314 4.686 54 8 54 H 34 C 37.314 54 40 51.314 40 48 V 18" stroke="{accent}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M 26 4 L 40 18 H 26 V 4 Z" fill="{accent}" fill-opacity="0.3" stroke="{accent}" stroke-width="2" stroke-linejoin="round"/>
    <path d="M 32 13 C 41 4 52 6 52 6 C 52 6 52 17 41 23 C 35.5 26 32 20 32 13 Z" stroke="{accent}" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M 33 17 Q 41 12 49 7" stroke="{accent}" stroke-width="2" stroke-linecap="round"/>
    <line x1="8" y1="13" x2="20" y2="13" stroke="{accent}" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="8" y1="20" x2="28" y2="20" stroke="{accent}" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="8" y1="27" x2="28" y2="27" stroke="{accent}" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="8" y1="34" x2="28" y2="34" stroke="{accent}" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="8" y1="41" x2="18" y2="41" stroke="{accent}" stroke-width="2.5" stroke-linecap="round"/>
    <path d="M 24 42 C 24 38.686 26.686 36 30 36 C 33.314 36 36 38.686 36 42 C 36 45.314 33.314 48 30 48 C 28.5 48 27.2 47.4 26.2 46.5 L 23 48.5 L 24.3 45.5 C 24.1 44.4 24 43.2 24 42 Z" stroke="{accent}" stroke-width="2" fill="{bg}" stroke-linejoin="round"/>
    <circle cx="27.5" cy="42" r="1" fill="{accent}"/>
    <circle cx="30" cy="42" r="1" fill="{accent}"/>
    <circle cx="32.5" cy="42" r="1" fill="{accent}"/>
</g>
"""


def render_logo(width=190, font_size=26, show_text=True):
    accent = token("accent-olive")
    text_main = token("text-main")
    bg = token("bg-app")
    icon = LOGO_ICON.format(accent=accent, bg=bg)
    height = round(width * 58 / 200)
    viewbox_width = 200 if show_text else 56

    text_svg = (
        f"""<text x="66" y="38" font-family="'Plus Jakarta Sans', sans-serif" font-size="{font_size}" letter-spacing="-0.5">
                    <tspan font-weight="700" fill="{text_main}">Docu</tspan>
                    <tspan font-weight="400" fill="{accent}">Sage</tspan>
                </text>"""
        if show_text
        else ""
    )

    st.markdown(
        f"""
        <div class="ds-logo-wrap">
            <svg width="{width}" height="{height}" viewBox="0 0 {viewbox_width} 58" fill="none" xmlns="http://www.w3.org/2000/svg">
                {icon}
                {text_svg}
            </svg>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar():
    with st.sidebar:
        st.markdown(DOCUMENTS_CSS, unsafe_allow_html=True)
        render_logo()

        if not get_state("documents_loaded"):
            refresh_documents()

        st.markdown('<div class="ds-section-label">Upload</div>', unsafe_allow_html=True)
        render_upload_widget(refresh_documents, key_suffix="sidebar")

        render_document_library()

        st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
        active_view = get_state("active_view")
        settings_type = "primary" if active_view == "settings" else "secondary"
        if st.button("Settings", key="nav_settings", use_container_width=True, type=settings_type):
            set_state("active_view", "settings")
            st.rerun()


SIDEBAR_CSS = """
<style>
.ds-logo-wrap {
    padding: 0.25rem 0 1rem 0;
}
</style>
"""
