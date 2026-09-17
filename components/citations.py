"""
Renders source citations as premium reference cards.

Only user-facing fields are ever shown: filename, page, relevance tier.
Technical retrieval fields (distance, chunk_id, embeddings) are never
rendered here — even if present on the source object. A future
developer mode (see utils/state.DEFAULTS["developer_mode"]) may surface
those fields for debugging, but that is intentionally not wired to any
UI control yet.
"""

import streamlit as st
from utils.state import get_state


def _relevance_label(relevance):
    """Map a numeric relevance score to a plain-language tier."""
    try:
        value = float(relevance)
    except (TypeError, ValueError):
        return "Relevant"
    if value >= 70:
        return "High"
    if value >= 40:
        return "Medium"
    return "Low"


def render_citation_card(source):
    filename = source.get("filename", "Document")
    page = source.get("page")
    relevance_label = _relevance_label(source.get("relevance"))

    page_text = f"Page {page}" if page is not None else ""

    debug_html = ""
    if get_state("developer_mode"):
        # Reserved for future developer mode. Not reachable today since
        # no UI control sets developer_mode to True.
        distance = source.get("distance")
        chunk_id = source.get("chunk_id")
        debug_html = f"""
        <div class="ds-citation-debug">
            distance: {distance} · chunk_id: {chunk_id}
        </div>
        """

    st.markdown(
        f"""
        <div class="ds-citation-card">
            <div class="ds-citation-icon">&#8227;</div>
            <div class="ds-citation-body">
                <div class="ds-citation-filename">{filename}</div>
                <div class="ds-citation-meta">
                    <span>{page_text}</span>
                    <span class="ds-citation-dot">&middot;</span>
                    <span class="ds-relevance ds-relevance-{relevance_label.lower()}">{relevance_label} relevance</span>
                </div>
            </div>
        </div>
        {debug_html}
        """,
        unsafe_allow_html=True,
    )


def render_citations(sources):
    if not sources:
        return
    st.markdown(
        """<div class="ds-citations-label">Sources</div>""",
        unsafe_allow_html=True,
    )
    for source in sources:
        render_citation_card(source)


CITATIONS_CSS = """
<style>
.ds-citations-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    margin: 0.6rem 0 0.4rem 0;
}
.ds-citation-card {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    background-color: var(--accent-sage-subtle);
    border-left: 3px solid var(--accent-olive);
    border-radius: 8px;
    padding: 0.55rem 0.75rem;
    margin-bottom: 0.4rem;
    transition: box-shadow 0.15s ease;
}
.ds-citation-card:hover {
    box-shadow: var(--shadow-glow);
}
.ds-citation-icon {
    color: var(--accent-olive);
    font-size: 0.85rem;
    line-height: 1.4;
}
.ds-citation-filename {
    font-weight: 600;
    font-size: 0.85rem;
    color: var(--text-main);
}
.ds-citation-meta {
    font-size: 0.78rem;
    color: var(--text-muted);
    display: flex;
    gap: 0.4rem;
    align-items: center;
    margin-top: 0.1rem;
}
.ds-citation-dot { opacity: 0.6; }
.ds-relevance-high { color: var(--accent-olive); font-weight: 600; }
.ds-relevance-medium { color: var(--text-muted); font-weight: 600; }
.ds-relevance-low { color: var(--text-muted); }
.ds-citation-debug {
    font-size: 0.7rem;
    color: var(--text-muted);
    margin: -0.3rem 0 0.4rem 0.75rem;
    opacity: 0.7;
}
</style>
"""
