"""
Shared "status flow" widget: a vertical checklist that steps through
stages one at a time (done / active / pending). Used by both the
upload experience and the chat thinking sequence so the two moments
where the user waits on the backend feel like the same product,
not two different loading patterns bolted together.
"""

import streamlit as st

STATUS_FLOW_CSS = """
<style>
.ds-flow {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    padding: 0.2rem 0;
}
.ds-flow-step {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    font-size: 0.9rem;
    transition: opacity 0.25s ease;
}
.ds-flow-icon {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
}
.ds-flow-done .ds-flow-icon {
    color: var(--accent-olive);
    font-weight: 700;
}
.ds-flow-done .ds-flow-label {
    color: var(--text-muted);
}
.ds-flow-active .ds-flow-label {
    color: var(--text-main);
    font-weight: 600;
}
.ds-flow-pending {
    opacity: 0.45;
}
.ds-flow-pending .ds-flow-icon {
    color: var(--text-muted);
}
.ds-flow-pending .ds-flow-label {
    color: var(--text-muted);
}
.ds-flow-spinner {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--accent-olive);
    display: inline-block;
    animation: ds-flow-blink 1s infinite ease-in-out;
}
@keyframes ds-flow-blink {
    0%, 100% { opacity: 0.3; transform: scale(0.8); }
    50% { opacity: 1; transform: scale(1); }
}
.ds-flow-error .ds-flow-icon {
    color: #C4554D;
}
.ds-flow-error .ds-flow-label {
    color: #C4554D;
    font-weight: 600;
}
</style>
"""


def render_status_flow(container, steps, active_index, error_index=None):
    """
    steps: list of label strings, e.g. ["Uploading document", "Processing document", ...]
    active_index: index of the step currently in progress (-1 means all pending,
        len(steps) means all complete)
    error_index: if set, that step renders in an error state instead of active/done
    """
    parts = ['<div class="ds-flow">']
    for i, label in enumerate(steps):
        if error_index is not None and i == error_index:
            state_class = "ds-flow-error"
            icon = "!"
        elif i < active_index or (error_index is None and active_index >= len(steps)):
            state_class = "ds-flow-done"
            icon = "&#10003;"
        elif i == active_index:
            state_class = "ds-flow-active"
            icon = '<span class="ds-flow-spinner"></span>'
        else:
            state_class = "ds-flow-pending"
            icon = "&#9675;"
        parts.append(
            f'<div class="ds-flow-step {state_class}">'
            f'<span class="ds-flow-icon">{icon}</span>'
            f'<span class="ds-flow-label">{label}</span>'
            f'</div>'
        )
    parts.append("</div>")
    container.markdown("".join(parts), unsafe_allow_html=True)
