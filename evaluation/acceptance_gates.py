"""
Item 14 — production acceptance thresholds and release certificates.

Eval (item 12) measures. The adversarial pack (item 13) regresses.
This module is release policy: hard pass/fail against frozen launch bars.

Empty held-out reports must not certify a ship. Rate gates do not apply
until the minimum evaluated-case floor is met (no vacuous 0% wrong-page pass).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from rerank_calibration import zero_result_when_fused
from visual_evidence import VISUAL_TYPES

PROFILE_CI = "ci"
PROFILE_RELEASE = "release"
VALID_PROFILES = {PROFILE_CI, PROFILE_RELEASE}

CMP_MIN = "min"
CMP_MAX = "max"
CMP_MIN_COUNT = "min_count"
CMP_TRUE = "true"


@dataclass(frozen=True)
class Thresholds:
    adversarial_pass_rate: float = 1.0
    retrieval_hit_rate: float = 0.92
    context_recall_rate: float = 0.90
    grounding_rate: float = 0.90
    localization_rate: float = 0.95
    wrong_page_rate_max: float = 0.02
    false_precise_rate_max: float = 0.01
    ui_dropout_rate_max: float = 0.0
    rerank_zero_result_rate_max: float = 0.0
    instability_rate_max: float = 0.05
    release_min_evaluated: int = 20
    release_min_native_evaluated: int = 10
    release_min_retrieval_evaluated: int = 10


DEFAULT_THRESHOLDS = Thresholds()


@dataclass
class GateResult:
    id: str
    passed: bool
    actual: float | int | None
    threshold: float | int | None
    comparator: str
    required: bool
    detail: str = ""


def probe_rerank_zero_result() -> float:
    """1.0 if a nonempty fused pool would send 0 chunks to the LLM."""
    from reranker import select_evidence, sigmoid_relevance

    candidates = [
        {
            "id": f"gate_{index}",
            "text": (
                f"Employment policy passage {index} describing written notice "
                "periods and annual reviews for staff."
            ),
            "metadata": {"document_id": "gate-doc", "page_number": index},
            "reranker_score": -6.0 - (index * 0.08),
            "relevance": sigmoid_relevance(-6.0 - (index * 0.08)),
            "rrf_score": 0.02,
            "sources": ["dense"],
        }
        for index in range(1, 8)
    ]
    selected = select_evidence(candidates, top_k=5)
    return 1.0 if zero_result_when_fused(len(candidates), len(selected)) else 0.0


def _rate(rows: list[dict[str, Any]], key: str, *, expect: bool = True) -> float | None:
    if not rows:
        return None
    hits = sum(1 for row in rows if bool(row.get(key)) is expect)
    return hits / len(rows)


def _is_native(row: dict[str, Any]) -> bool:
    kind = str(row.get("content_type") or "native_text").strip()
    return kind not in VISUAL_TYPES


def summarize_eval(eval_report: dict[str, Any] | None) -> dict[str, Any]:
    report = eval_report or {}
    rows = [
        row
        for row in (report.get("cases") or [])
        if isinstance(row, dict) and not row.get("skipped")
    ]
    native = [row for row in rows if _is_native(row)]
    retrieval = [row for row in rows if row.get("retrieval_hit") is not None]
    return {
        "evaluated": len(rows),
        "native_evaluated": len(native),
        "retrieval_evaluated": len(retrieval),
        "localization_rate": _rate(native, "localized"),
        "ui_dropout_rate": _rate(native, "ui_dropout"),
        "wrong_page_rate": _rate(rows, "wrong_page"),
        "false_precise_rate": _rate(rows, "false_precise"),
        "grounding_rate": _rate(rows, "unsupported_claim", expect=False),
        "retrieval_hit_rate": _rate(retrieval, "retrieval_hit"),
        "context_recall_rate": _rate(retrieval, "retrieval_hit"),
    }


def adversarial_pass_rate(adversarial: dict[str, Any] | None) -> float | None:
    if not adversarial:
        return None
    python = adversarial.get("python") if "python" in adversarial else adversarial
    if not isinstance(python, dict):
        return None
    ran = int(python.get("tests_run") or 0)
    if ran <= 0:
        return 0.0
    if python.get("passed") is False or adversarial.get("passed") is False:
        ok = int(python.get("ok") or 0)
        return max(0.0, min(1.0, ok / ran))
    ok = int(python.get("ok") or ran)
    return max(0.0, min(1.0, ok / ran))


def _gate(
    gate_id: str,
    *,
    actual: float | int | None,
    threshold: float | int | None,
    comparator: str,
    required: bool,
    detail: str = "",
) -> GateResult:
    passed = False
    if actual is None:
        passed = not required
        detail = detail or "missing"
    elif comparator == CMP_MIN:
        passed = float(actual) >= float(threshold or 0)
    elif comparator == CMP_MAX:
        passed = float(actual) <= float(threshold or 0)
    elif comparator == CMP_MIN_COUNT:
        passed = int(actual) >= int(threshold or 0)
    elif comparator == CMP_TRUE:
        passed = bool(actual)
    return GateResult(
        id=gate_id,
        passed=passed,
        actual=actual,
        threshold=threshold,
        comparator=comparator,
        required=required,
        detail=detail,
    )


def evaluate_certificate(
    *,
    profile: str,
    adversarial: dict[str, Any] | None = None,
    eval_report: dict[str, Any] | None = None,
    rerank_zero_result_rate: float | None = None,
    instability_rate: float | None = None,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    """
    Build a pass/fail certificate for `ci` (engineering) or `release` (ship).
    """
    if profile not in VALID_PROFILES:
        raise ValueError(f"unknown profile: {profile}")
    release = profile == PROFILE_RELEASE
    metrics = summarize_eval(eval_report)
    adv_rate = adversarial_pass_rate(adversarial)
    if rerank_zero_result_rate is None:
        rerank_zero_result_rate = probe_rerank_zero_result()
    if instability_rate is None:
        instability_rate = 0.0 if (adv_rate is not None and adv_rate >= 1.0) else (
            1.0 if adv_rate is not None else None
        )

    gates: list[GateResult] = [
        _gate(
            "adversarial_pack",
            actual=adv_rate,
            threshold=thresholds.adversarial_pass_rate,
            comparator=CMP_MIN,
            required=True,
            detail="item 13 pack must be 100%",
        ),
        _gate(
            "rerank_zero_result",
            actual=rerank_zero_result_rate,
            threshold=thresholds.rerank_zero_result_rate_max,
            comparator=CMP_MAX,
            required=True,
            detail="nonempty fused pool must not yield 0 LLM slots",
        ),
        _gate(
            "instability",
            actual=instability_rate,
            threshold=thresholds.instability_rate_max,
            comparator=CMP_MAX,
            required=True,
            detail="same claim x3 must stay stable (<=5%)",
        ),
    ]

    if release:
        gates.extend(
            [
                _gate(
                    "held_out_evaluated",
                    actual=metrics["evaluated"],
                    threshold=thresholds.release_min_evaluated,
                    comparator=CMP_MIN_COUNT,
                    required=True,
                    detail="held-out real-PDF cases, not the empty catalog",
                ),
                _gate(
                    "held_out_native_evaluated",
                    actual=metrics["native_evaluated"],
                    threshold=thresholds.release_min_native_evaluated,
                    comparator=CMP_MIN_COUNT,
                    required=True,
                    detail="native-text localization sample",
                ),
                _gate(
                    "held_out_retrieval_evaluated",
                    actual=metrics["retrieval_evaluated"],
                    threshold=thresholds.release_min_retrieval_evaluated,
                    comparator=CMP_MIN_COUNT,
                    required=True,
                    detail="retrieval-mode cases for Recall@pool",
                ),
            ]
        )
        volume_ok = (
            int(metrics["evaluated"] or 0) >= thresholds.release_min_evaluated
            and int(metrics["native_evaluated"] or 0)
            >= thresholds.release_min_native_evaluated
        )
        retrieval_ok = (
            int(metrics["retrieval_evaluated"] or 0)
            >= thresholds.release_min_retrieval_evaluated
        )
        gates.extend(
            [
                _gate(
                    "localization_native",
                    actual=metrics["localization_rate"] if volume_ok else None,
                    threshold=thresholds.localization_rate,
                    comparator=CMP_MIN,
                    required=True,
                    detail="native-text localization >= 95%",
                ),
                _gate(
                    "ui_dropout_native",
                    actual=metrics["ui_dropout_rate"] if volume_ok else None,
                    threshold=thresholds.ui_dropout_rate_max,
                    comparator=CMP_MAX,
                    required=True,
                    detail="native-text citation UI dropout = 0%",
                ),
                _gate(
                    "wrong_page",
                    actual=metrics["wrong_page_rate"] if volume_ok else None,
                    threshold=thresholds.wrong_page_rate_max,
                    comparator=CMP_MAX,
                    required=True,
                    detail="wrong-page <= 2%",
                ),
                _gate(
                    "false_precise",
                    actual=metrics["false_precise_rate"] if volume_ok else None,
                    threshold=thresholds.false_precise_rate_max,
                    comparator=CMP_MAX,
                    required=True,
                    detail="false-precise highlight <= 1%",
                ),
                _gate(
                    "grounding",
                    actual=metrics["grounding_rate"] if volume_ok else None,
                    threshold=thresholds.grounding_rate,
                    comparator=CMP_MIN,
                    required=True,
                    detail="supported claims >= 90%",
                ),
                _gate(
                    "retrieval_hit",
                    actual=metrics["retrieval_hit_rate"] if retrieval_ok else None,
                    threshold=thresholds.retrieval_hit_rate,
                    comparator=CMP_MIN,
                    required=True,
                    detail="Recall@pool >= 92%",
                ),
                _gate(
                    "context_recall",
                    actual=metrics["context_recall_rate"] if retrieval_ok else None,
                    threshold=thresholds.context_recall_rate,
                    comparator=CMP_MIN,
                    required=True,
                    detail="post-rerank context recall >= 90%",
                ),
            ]
        )

    blockers = [
        gate.id
        for gate in gates
        if gate.required and not gate.passed
    ]
    certified = not blockers
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "certified": certified,
        "human_signoff_required": release,
        "thresholds": asdict(thresholds),
        "metrics": metrics,
        "gates": [asdict(gate) for gate in gates],
        "blockers": blockers,
    }
