"""
Item 15 — final E2E stress / launch readiness audit.

Repeats the held-out suite, the 9 generic production-audit scenarios,
load/latency, and failure injection. Requires a certified item-14 release
stamp. Human sign-off is required for launch_approved; this command is not
a substitute for items 12/14.

Usage (from repo root):
  python -m evaluation.run_launch_audit
  python -m evaluation.run_launch_audit --signoff
  python -m evaluation.run_launch_audit --run-release --signoff
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation.acceptance_gates import PROFILE_RELEASE, summarize_eval
from evaluation.held_out_handbook import HELD_OUT_DOCUMENT_ID
from evaluation.held_out_runtime import held_out_eval_environment
from evaluation.launch_audit import (
    P95_LATENCY_MS_MAX,
    PRODUCTION_SCENARIOS,
    evaluate_launch_audit,
    failure_injection_probes,
)
from evaluation.run_acceptance_gates import RESULTS_PATH as ACCEPTANCE_PATH
from evaluation.run_acceptance_gates import main as run_acceptance_main
from evaluation.run_real_document_eval import _normalize_blob

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
RESULTS_PATH = RESULTS_DIR / "launch_audit_latest.json"


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else None


def _pool_blob(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for row in list(payload.get("sources") or []) + list(
        payload.get("recall_candidates") or []
    ):
        if not isinstance(row, dict):
            continue
        for key in ("text", "snippet", "quote", "chunk_text"):
            parts.append(str(row.get(key) or ""))
    return _normalize_blob(" ".join(parts))


def _rank1_id(payload: dict[str, Any]) -> str:
    sources = list(payload.get("sources") or [])
    if sources and isinstance(sources[0], dict):
        return str(sources[0].get("chunk_id") or sources[0].get("id") or "")
    recall = list(payload.get("recall_candidates") or [])
    if recall and isinstance(recall[0], dict):
        return str(recall[0].get("chunk_id") or recall[0].get("id") or "")
    return ""


def _ask(question: str) -> dict[str, Any]:
    from rag import ask_question

    return ask_question(
        question,
        document_ids=[HELD_OUT_DOCUMENT_ID],
        generate=False,
    )


def _run_scenarios() -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    hits = 0
    for spec in PRODUCTION_SCENARIOS:
        started = time.perf_counter()
        try:
            payload = _ask(str(spec["question"]))
            error = None
        except Exception as exc:
            payload = {}
            error = f"{exc.__class__.__name__}: {exc}"
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        needle = _normalize_blob(str(spec["needle"]))
        hit = bool(needle) and needle in _pool_blob(payload)
        if hit:
            hits += 1
        rows.append(
            {
                "id": spec["id"],
                "audit_analog": spec["audit_analog"],
                "question": spec["question"],
                "needle": spec["needle"],
                "hit": hit,
                "latency_ms": round(elapsed_ms, 1),
                "rank1_id": _rank1_id(payload),
                "error": error,
            }
        )
    return rows, hits, len(PRODUCTION_SCENARIOS)


def _run_qx3(question: str) -> tuple[bool, list[str]]:
    ids: list[str] = []
    for _ in range(3):
        payload = _ask(question)
        ids.append(_rank1_id(payload))
    stable = bool(ids) and len(set(ids)) == 1 and all(ids)
    return stable, ids


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = 0.95 * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return float(ordered[low] * (1.0 - frac) + ordered[high] * frac)


def _print_audit(report: dict[str, Any]) -> None:
    engineering = bool(report.get("engineering_passed"))
    approved = bool(report.get("launch_approved"))
    print(f"Launch audit engineering: {'PASS' if engineering else 'FAIL'}")
    print(f"Launch approved: {'YES' if approved else 'NO'}")
    if report.get("human_signoff_required") and not report.get("human_signoff"):
        print("Human sign-off is still required (--signoff after review).")
    for probe in report.get("failure_injection") or []:
        mark = "PASS" if probe.get("passed") else "FAIL"
        print(f"  [{mark}] {probe.get('id')}: {probe.get('detail')}")
    scenarios = report.get("scenarios") or []
    if scenarios:
        print("Production scenarios:")
        for row in scenarios:
            mark = "HIT" if row.get("hit") else "MISS"
            print(f"  [{mark}] {row.get('id')}: {row.get('needle')}")
    blockers = report.get("blockers") or []
    if blockers:
        print("Blockers: " + ", ".join(str(item) for item in blockers))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Item 15 launch readiness audit (not a substitute for item 14)"
    )
    parser.add_argument("--certificate", default=str(ACCEPTANCE_PATH))
    parser.add_argument(
        "--run-release",
        action="store_true",
        help="Run item 14 --profile release before the audit",
    )
    parser.add_argument(
        "--signoff",
        action="store_true",
        help="Record human sign-off for this run (launch_approved)",
    )
    parser.add_argument("--out", default=str(RESULTS_PATH))
    parser.add_argument("--skip-index", action="store_true")
    args = parser.parse_args(argv)

    if args.run_release:
        release_code = run_acceptance_main(["--profile", PROFILE_RELEASE])
        if release_code != 0:
            print("Item 14 release gate failed; item 15 will not approve launch.")

    certificate = _load_json(Path(args.certificate)) or {}
    release_certified = bool(certificate.get("certified")) and (
        str(certificate.get("profile") or "") == PROFILE_RELEASE
    )
    metrics = certificate.get("metrics") or summarize_eval(
        certificate.get("eval_report") or {}
    )
    held_out_evaluated = int(metrics.get("evaluated") or 0)

    scenario_rows: list[dict[str, Any]] = []
    scenario_hits = 0
    scenario_total = len(PRODUCTION_SCENARIOS)
    qx3_stable = False
    qx3_ids: list[str] = []
    latencies: list[float] = []

    with held_out_eval_environment(index=not args.skip_index) as _runtime:
        scenario_rows, scenario_hits, scenario_total = _run_scenarios()
        latencies = [float(row.get("latency_ms") or 0.0) for row in scenario_rows]
        qx3_stable, qx3_ids = _run_qx3(str(PRODUCTION_SCENARIOS[0]["question"]))

    p95 = _p95(latencies)
    probes = failure_injection_probes()
    # Ghost-doc probe uses the live registry. Inside the isolate the ghost id
    # is still unknown, so the default probe remains valid. Re-run after the
    # context exits so Super Focused/empty-allowlist stay process-global.
    policy = evaluate_launch_audit(
        release_certified=release_certified,
        held_out_evaluated=held_out_evaluated,
        scenario_hits=scenario_hits,
        scenario_total=scenario_total,
        qx3_stable=qx3_stable,
        p95_latency_ms=p95,
        failure_probes=probes,
        human_signoff=bool(args.signoff),
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release_certified": release_certified,
        "held_out_evaluated": held_out_evaluated,
        "scenarios": scenario_rows,
        "scenario_hits": scenario_hits,
        "scenario_total": scenario_total,
        "qx3_stable": qx3_stable,
        "qx3_rank1_ids": qx3_ids,
        "latency_ms": {
            "n": len(latencies),
            "p50": round(statistics.median(latencies), 1) if latencies else None,
            "p95": round(p95, 1) if p95 is not None else None,
            "max": round(max(latencies), 1) if latencies else None,
            "threshold_p95": P95_LATENCY_MS_MAX,
        },
        **policy,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print_audit(report)
    print(f"Written: {out_path}")
    if not report.get("engineering_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
