"""
DocuSage — app entrypoint.

This file is intentionally thin: page config, state bootstrap, theme
injection, and routing into components/. No business logic lives here.
"""

import streamlit as st

from utils.state import init_state, get_state, set_state
from components.theme import inject_theme
from components.sidebar import render_sidebar, SIDEBAR_CSS
from components.chat import render_chat_area
from components.settings import render_settings_page, SETTINGS_CSS
from components.documents import render_document_info_panel
from components.status import STATUS_FLOW_CSS
from components.upload import UPLOAD_CSS

st.set_page_config(
    page_title="DocuSage",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

init_state()
inject_theme()
st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
st.markdown(SETTINGS_CSS, unsafe_allow_html=True)
st.markdown(STATUS_FLOW_CSS, unsafe_allow_html=True)
st.markdown(UPLOAD_CSS, unsafe_allow_html=True)

render_sidebar()

active_view = get_state("active_view")

if active_view == "settings":
    render_settings_page()
else:
    selected_document = get_state("selected_document")
    show_panel = get_state("show_info_panel") and selected_document is not None

    if show_panel:
        main_col, panel_col = st.columns([4, 1.1], gap="large")
    else:
        main_col = st.container()
        panel_col = None

    with main_col:
        if selected_document:
            header_col, toggle_col = st.columns([6, 1])
            with toggle_col:
                label = "Hide details" if get_state("show_info_panel") else "Details"
                if st.button(label, key="toggle_info_panel", use_container_width=True):
                    set_state("show_info_panel", not get_state("show_info_panel"))
                    st.rerun()
        render_chat_area()

    if panel_col is not None:
        with panel_col:
            render_document_info_panel()
