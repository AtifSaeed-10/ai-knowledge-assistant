"""
Item 14 — production acceptance / release certification CLI.

Profiles
  ci       engineering gate (adversarial pack + rerank invariant)
  release  world-deploy stamp (ci + held-out real-PDF thresholds)

Empty `evaluation/real_document_cases.json` cannot certify a release.

Usage (from repo root):
  python -m evaluation.run_acceptance_gates --profile ci
  python -m evaluation.run_acceptance_gates --profile release
  python -m evaluation.run_acceptance_gates --profile ci --adversarial-report evaluation/results/adversarial_latest.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from evaluation.acceptance_gates import (
    PROFILE_CI,
    PROFILE_RELEASE,
    VALID_PROFILES,
    evaluate_certificate,
)
from evaluation.held_out_runtime import cases_use_held_out, run_held_out_evaluation
from evaluation.run_adversarial_suite import run_python_pack
from evaluation.run_real_document_eval import CASES_PATH, load_cases, run_evaluation


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
RESULTS_PATH = RESULTS_DIR / "acceptance_latest.json"


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else None


def _print_certificate(cert: dict[str, Any]) -> None:
    profile = str(cert.get("profile") or "")
    certified = bool(cert.get("certified"))
    title = "CI engineering gate" if profile == PROFILE_CI else "Release certification"
    print(f"{title}: {'CERTIFIED' if certified else 'NOT CERTIFIED'}")
    if cert.get("human_signoff_required"):
        print("Automated stamp is not a substitute for the item-15 launch audit.")
    for gate in cert.get("gates") or []:
        mark = "PASS" if gate.get("passed") else "FAIL"
        print(
            f"  [{mark}] {gate.get('id')}: actual={gate.get('actual')} "
            f"{gate.get('comparator')} {gate.get('threshold')}"
        )
        if gate.get("detail"):
            print(f"         {gate['detail']}")
    blockers = cert.get("blockers") or []
    if blockers:
        print("Blockers: " + ", ".join(str(item) for item in blockers))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Certify the build against frozen production acceptance gates"
    )
    parser.add_argument(
        "--profile",
        choices=sorted(VALID_PROFILES),
        default=PROFILE_RELEASE,
        help="ci = engineering gate; release = ship stamp (default)",
    )
    parser.add_argument("--adversarial-report", default=None)
    parser.add_argument("--eval-report", default=None)
    parser.add_argument(
        "--skip-adversarial",
        action="store_true",
        help="Do not run the item-13 pack (pass --adversarial-report instead)",
    )
    parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="Do not run held-out real-document eval",
    )
    parser.add_argument("--out", default=str(RESULTS_PATH))
    args = parser.parse_args(argv)

    adversarial = _load_json(
        Path(args.adversarial_report) if args.adversarial_report else None
    )
    if adversarial is None and not args.skip_adversarial:
        python_report = run_python_pack(skip_slow=False)
        adversarial = {
            "passed": bool(python_report.get("passed")),
            "python": python_report,
        }

    eval_report = _load_json(Path(args.eval_report) if args.eval_report else None)
    if eval_report is None and not args.skip_eval and args.profile == PROFILE_RELEASE:
        cases = load_cases(CASES_PATH)
        if cases:
            if cases_use_held_out(cases):
                eval_report = run_held_out_evaluation(cases, index=True)
            else:
                eval_report = asdict(run_evaluation(cases))
        else:
            eval_report = {
                "case_count": 0,
                "evaluated": 0,
                "skipped": 0,
                "cases": [],
            }

    cert = evaluate_certificate(
        profile=args.profile,
        adversarial=adversarial,
        eval_report=eval_report,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cert, indent=2), encoding="utf-8")
    _print_certificate(cert)
    print(f"Written: {out_path}")
    return 0 if cert.get("certified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
