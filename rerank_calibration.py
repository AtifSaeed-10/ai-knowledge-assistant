"""
Item 3 — reranker score calibration and pre-LLM rank diagnostics.

MiniLM (ms-marco) logits are systematically more negative than BGE. Mapping
them through an unshifted sigmoid made true positives look like 1% relevance
and tripped evidence/citation floors. Offsets below are fitted to the held-out
audit score table (not to individual product questions).
"""

from __future__ import annotations

import math
from typing import Any

from config import (
    BGE_LOGIT_OFFSET,
    CITATION_MIN_RELEVANCE,
    EVIDENCE_MIN_RELEVANCE,
    MINILM_LOGIT_OFFSET,
    RERANK_TIE_MARGIN,
    RERANKER_MODEL,
    RERANKER_MODEL_BGE,
    RERANKER_MODEL_MINILM,
)

# Frozen MiniLM logits from the production audit (held-out vs shipping prompts).
AUDIT_HELD_OUT_MINILM: tuple[dict[str, Any], ...] = (
    {
        "case_id": "entropy_why",
        "raw_score": -4.4518,
        "label": "true_positive",
        "must_clear_evidence_floor": True,
        "must_clear_citation_floor": True,
    },
    {
        "case_id": "world_cup",
        "raw_score": -5.9783,
        "label": "true_negative",
        "must_clear_evidence_floor": False,
        "must_clear_citation_floor": False,
    },
    {
        "case_id": "france_capital",
        "raw_score": -10.9996,
        "label": "true_negative",
        "must_clear_evidence_floor": False,
        "must_clear_citation_floor": False,
    },
)


def is_minilm_reranker(model_name: str | None) -> bool:
    name = (model_name or "").strip().lower()
    return "minilm" in name or "ms-marco" in name


def logit_offset_for_model(model_name: str | None) -> float:
    if is_minilm_reranker(model_name):
        return float(MINILM_LOGIT_OFFSET)
    return float(BGE_LOGIT_OFFSET)


def resolve_rerank_model_name(model_name: str | None) -> str:
    if isinstance(model_name, str) and model_name.strip():
        return model_name.strip()
    return RERANKER_MODEL


def _stable_sigmoid_relevance(score: float) -> int:
    if score >= 0:
        z = math.exp(-score)
        prob = 1.0 / (1.0 + z)
    else:
        z = math.exp(score)
        prob = z / (1.0 + z)
    return int(max(0, min(100, round(prob * 100))))


def calibrated_relevance(
    score: float,
    model_name: str | None = None,
) -> int:
    """Map a raw cross-encoder logit to [0, 100] with a model-specific shift."""
    offset = logit_offset_for_model(resolve_rerank_model_name(model_name))
    return _stable_sigmoid_relevance(float(score) + offset)


def adaptive_keep_candidates(
    candidates: list[dict[str, Any]],
    min_relevance: int | None = None,
    tie_margin: float | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """
    Choose the gating set before near-dup / page diversification.

    Paths:
      floor_or_tie — at least one chunk meets the evidence floor; also keep
                     below-floor neighbors within RERANK_TIE_MARGIN of the top
      dual_source  — MiniLM-style rescue when the floor would empty the pool
      recall_fallback — Item 2: nonempty pool never becomes 0 slots
      empty
    """
    from reranker import dual_source_fallback_candidates, filter_min_relevance

    if not candidates:
        return [], "empty"

    floor = EVIDENCE_MIN_RELEVANCE if min_relevance is None else int(min_relevance)
    margin = RERANK_TIE_MARGIN if tie_margin is None else float(tie_margin)
    above = filter_min_relevance(candidates, floor)
    if above:
        scored = [
            item
            for item in candidates
            if item.get("reranker_score") is not None
        ]
        if not scored:
            return above, "floor_or_tie"
        top_score = max(float(item["reranker_score"]) for item in scored)
        kept: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in candidates:
            marker = str(item.get("id") or id(item))
            rel = int(item.get("relevance") or 0)
            raw = item.get("reranker_score")
            near_tie = (
                raw is not None
                and (top_score - float(raw)) <= margin
                and rel < floor
            )
            if rel >= floor or near_tie:
                if near_tie:
                    item["rerank_tie"] = True
                if marker not in seen:
                    seen.add(marker)
                    kept.append(item)
        return kept, "floor_or_tie"

    dual = dual_source_fallback_candidates(candidates)
    if dual:
        return dual, "dual_source"
    return list(candidates), "recall_fallback"


def _page_from_metadata(metadata: dict[str, Any] | None) -> int | None:
    if not metadata:
        return None
    value = metadata.get("page_number")
    if value is None:
        value = metadata.get("page_start")
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    if page < 1:
        return None
    return page


def pre_llm_rank_diagnostics(
    selected: list[dict[str, Any]],
) -> dict[str, Any]:
    """Page/rank snapshot after rerank, before the LLM writes an answer."""
    if not selected:
        return {
            "rank1_id": None,
            "rank1_page": None,
            "retrieval_pages": [],
            "score_gap_12": None,
            "selected_count": 0,
            "gating_path": None,
        }

    first = selected[0]
    second = selected[1] if len(selected) > 1 else None
    gap = None
    first_score = first.get("reranker_score")
    second_score = second.get("reranker_score") if second else None
    if first_score is not None and second_score is not None:
        gap = round(float(first_score) - float(second_score), 4)

    pages: list[int] = []
    for item in selected:
        page = _page_from_metadata(item.get("metadata") or {})
        if page is not None:
            pages.append(page)

    return {
        "rank1_id": first.get("id"),
        "rank1_page": _page_from_metadata(first.get("metadata") or {}),
        "retrieval_pages": pages,
        "score_gap_12": gap,
        "selected_count": len(selected),
        "gating_path": first.get("gating_path"),
    }


def wrong_page_pre_llm(
    selected: list[dict[str, Any]],
    expected_page: int | None,
) -> bool:
    """
    True when rank-1 (the chunk E1 still binds to) is a different page
    than the labeled expected evidence page.
    """
    if expected_page is None:
        return False
    try:
        expected = int(expected_page)
    except (TypeError, ValueError):
        return False
    page = pre_llm_rank_diagnostics(selected).get("rank1_page")
    if page is None:
        return False
    return int(page) != expected


def zero_result_when_fused(fused_count: int, selected_count: int) -> bool:
    return int(fused_count) > 0 and int(selected_count) == 0


# Re-export model ids so tests can pin MiniLM vs BGE without importing config
# aliases in every file.
MINILM_MODEL = RERANKER_MODEL_MINILM
BGE_MODEL = RERANKER_MODEL_BGE
CITATION_FLOOR = CITATION_MIN_RELEVANCE
EVIDENCE_FLOOR = EVIDENCE_MIN_RELEVANCE
