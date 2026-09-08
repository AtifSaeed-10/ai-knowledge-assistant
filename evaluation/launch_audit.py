"""
Item 15 — launch-audit probes that do not need a live index.

The CLI (run_launch_audit) adds held-out replay, the 9 generic production
scenarios, load/latency, and human sign-off. This module is the
deterministic failure-injection slice and the audit pass/fail policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from citation_resolver import resolve_evidence_markers
from claim_validator import finalize_answer_citations
from index_hygiene import (
    chroma_where_for_document_ids,
    filter_hits_to_documents,
    resolve_retrieval_scope,
)
from modes import MODE_NORMAL, MODE_SUPER_FOCUSED

# Generic replay of the original 9-question production audit, as document-agnostic
# scenarios against the held-out handbook (not the demo PDFs).
PRODUCTION_SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": "definitional_fact",
        "audit_analog": "supervised-learning success path",
        "question": "How many days of written notice are required to terminate employment?",
        "needle": "thirty days written notice",
    },
    {
        "id": "competing_similar_passages",
        "audit_analog": "WWI trigger vs nearby treaty prose",
        "question": "How many days of written notice are required to terminate employment?",
        "needle": "thirty days written notice",
    },
    {
        "id": "figure_caption",
        "audit_analog": "figure depiction question",
        "question": "Which figure depicts the encoding stage used during handbook ingestion?",
        "needle": "Pipeline overview of the encoding stage",
    },
    {
        "id": "comparison_procedures",
        "audit_analog": "alliance plans comparison",
        "question": "How do dual-control expense approvals differ from ordinary spend?",
        "needle": "dual-control expense approvals above five thousand",
    },
    {
        "id": "multi_item_compromise",
        "audit_analog": "named-party compromise list",
        "question": "What does the office pantry restock include?",
        "needle": "tea, coffee, and oat biscuits",
    },
    {
        "id": "alias_note_on_names",
        "audit_analog": "alternate spelling / note on names",
        "question": "What was the Operations Unit formerly called?",
        "needle": "formerly Support Desk",
    },
    {
        "id": "dedication_front_matter",
        "audit_analog": "dedication / front-matter miss",
        "question": "Who is this operations handbook dedicated to?",
        "needle": "dedicated to Mira Chen and Omar Haddad",
    },
    {
        "id": "article_number",
        "audit_analog": "article-number citation",
        "question": "What retention window does Article 12 set?",
        "needle": "eighteen-month data-retention window",
    },
    {
        "id": "list_of_inputs",
        "audit_analog": "list of long-term causes",
        "question": "What three long-term inputs does the January performance-review cycle use?",
        "needle": "output quality, peer feedback, and customer outcomes",
    },
)

P95_LATENCY_MS_MAX = 180_000.0


@dataclass
class ProbeResult:
    id: str
    passed: bool
    detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def probe_ghost_document_isolation() -> ProbeResult:
    scoped, abort = resolve_retrieval_scope(MODE_NORMAL, ["ghost-doc-missing"])
    passed = (not abort) and scoped == []
    return ProbeResult(
        id="ghost_document_isolation",
        passed=passed,
        detail="unknown document ids must not fall back to the rest of the corpus",
        extra={"scoped": list(scoped), "abort": bool(abort)},
    )


def probe_super_focused_empty_aborts() -> ProbeResult:
    scoped, abort = resolve_retrieval_scope(MODE_SUPER_FOCUSED, [])
    passed = abort is True and scoped == []
    return ProbeResult(
        id="super_focused_empty_aborts",
        passed=passed,
        detail="Super Focused with no selection must abort rather than search the library",
        extra={"scoped": list(scoped), "abort": bool(abort)},
    )


def probe_empty_allowlist_drops_hits() -> ProbeResult:
    hits = [
        {"id": "a_0", "metadata": {"document_id": "a"}},
        {"id": "b_0", "metadata": {"document_id": "b"}},
    ]
    filtered = filter_hits_to_documents(hits, [])
    where = chroma_where_for_document_ids([])
    passed = filtered == [] and where is None
    return ProbeResult(
        id="empty_allowlist_drops_hits",
        passed=passed,
        detail="empty allowlist drops hits instead of searching all of Chroma",
        extra={"filtered": len(filtered), "where": where},
    )


def probe_invented_marker_stripped() -> ProbeResult:
    valid = {"E1"}
    text = 'Invented marker.[E99]\nReal claim.[E1]\nBox.[E1:"x0=10 y0=20 x1=400 y1=500"]'
    resolved = resolve_evidence_markers(text, valid)
    passed = "[E99]" not in resolved and "[E1]" in resolved and "x0" not in resolved
    finalized, _sources = finalize_answer_citations(
        "The policy is silent. [E99]",
        [],
        resolve_regions=False,
    )
    passed = passed and "[E99]" not in (finalized or "")
    return ProbeResult(
        id="invented_marker_stripped",
        passed=passed,
        detail="invented markers and coordinate payloads must not become citations",
        extra={"resolved": resolved, "finalized": finalized},
    )


def failure_injection_probes() -> list[ProbeResult]:
    return [
        probe_ghost_document_isolation(),
        probe_super_focused_empty_aborts(),
        probe_empty_allowlist_drops_hits(),
        probe_invented_marker_stripped(),
    ]


def evaluate_launch_audit(
    *,
    release_certified: bool,
    held_out_evaluated: int,
    scenario_hits: int,
    scenario_total: int,
    qx3_stable: bool,
    p95_latency_ms: float | None,
    failure_probes: list[ProbeResult],
    human_signoff: bool,
    p95_max_ms: float = P95_LATENCY_MS_MAX,
) -> dict[str, Any]:
    """
    Item 15 policy: not a substitute for item 14. Human sign-off is required
    for launch_approved; engineering_passed can be true without it.
    """
    probes = list(failure_probes)
    scenario_ok = scenario_total > 0 and scenario_hits == scenario_total
    latency_ok = p95_latency_ms is not None and float(p95_latency_ms) <= p95_max_ms
    injection_ok = all(item.passed for item in probes)
    engineering_passed = (
        bool(release_certified)
        and int(held_out_evaluated) >= 20
        and scenario_ok
        and bool(qx3_stable)
        and latency_ok
        and injection_ok
    )
    blockers: list[str] = []
    if not release_certified:
        blockers.append("release_not_certified")
    if int(held_out_evaluated) < 20:
        blockers.append("held_out_replay_short")
    if not scenario_ok:
        blockers.append("production_scenarios")
    if not qx3_stable:
        blockers.append("qx3_instability")
    if not latency_ok:
        blockers.append("latency_p95")
    if not injection_ok:
        blockers.append("failure_injection")
    launch_approved = engineering_passed and bool(human_signoff)
    if engineering_passed and not human_signoff:
        blockers.append("human_signoff_required")
    return {
        "engineering_passed": engineering_passed,
        "launch_approved": launch_approved,
        "human_signoff": bool(human_signoff),
        "human_signoff_required": True,
        "blockers": blockers,
        "failure_injection": [asdict(item) for item in probes],
        "thresholds": {
            "held_out_min": 20,
            "scenario_hits": f"{scenario_hits}/{scenario_total}",
            "p95_latency_ms_max": p95_max_ms,
        },
    }
