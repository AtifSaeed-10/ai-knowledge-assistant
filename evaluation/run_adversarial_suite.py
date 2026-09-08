"""
Item 13 — adversarial + regression gate.

Runs a frozen pack of deterministic tests that lock production failure
modes (scope bleed, invented citations, unstable binding, visual lies,
refusals on unrelated questions) plus the item 1–12 regression modules.

Does not change retrieval, chunking, embeddings, BM25, RRF, or E-ID assignment.
Does not call a live LLM.

Usage (from repo root):
  python -m evaluation.run_adversarial_suite
  python -m evaluation.run_adversarial_suite --skip-slow
  python -m evaluation.run_adversarial_suite --frontend
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_PATH = RESULTS_DIR / "adversarial_latest.json"

ADVERSARIAL_MODULES = ("test_adversarial_suite",)

REGRESSION_MODULES = (
    "test_index_hygiene",
    "test_recall_first_retrieval",
    "test_rerank_calibration",
    "test_query_retrieval",
    "test_claim_orchestrator",
    "test_claim_reanchor",
    "test_grounding_verifier",
    "test_citation_evidence_state",
    "test_citation_resolver",
    "test_claim_validator",
    "test_visual_evidence",
    "test_evidence_trace",
    "test_stream_final_answer",
    "test_acceptance_gates",
    "test_launch_audit",
)

SLOW_MODULES = ("test_real_document_eval", "test_held_out_catalog")

FRONTEND_VITEST_FILES = (
    "src/lib/citations/adversarial.test.ts",
    "src/lib/citations/evidenceStatus.test.ts",
    "src/lib/citations/markers.test.ts",
)


def _load_modules(names: tuple[str, ...]) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in names:
        suite.addTests(loader.loadTestsFromName(name))
    return suite


def _case_id(test: unittest.TestCase) -> str:
    return getattr(test, "id", lambda: str(test))()


def _module_of(test_id: str) -> str:
    return test_id.split(".")[0] if test_id else ""


def _failures(result: unittest.TestResult) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for test, traceback in list(result.failures) + list(result.errors):
        rows.append(
            {
                "id": _case_id(test),
                "module": _module_of(_case_id(test)),
                "kind": "error" if (test, traceback) in result.errors else "fail",
                "message": (traceback or "").strip().splitlines()[-1] if traceback else "",
            }
        )
    return rows


def run_python_pack(
    *,
    skip_slow: bool = False,
) -> dict[str, Any]:
    os.chdir(REPO)
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))

    names = ADVERSARIAL_MODULES + REGRESSION_MODULES
    if not skip_slow:
        names = names + SLOW_MODULES
    suite = _load_modules(names)
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    failed = _failures(result)
    ran = result.testsRun
    passed = ran - len(result.failures) - len(result.errors) - len(result.skipped)
    return {
        "passed": result.wasSuccessful(),
        "tests_run": ran,
        "ok": passed,
        "failed": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "failures": failed,
        "modules": list(names),
    }


def run_frontend_pack() -> dict[str, Any] | None:
    frontend = REPO / "frontend"
    if not (frontend / "node_modules").is_dir():
        return None
    cmd = ["npm", "test", "--", *FRONTEND_VITEST_FILES]
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(frontend),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
    except FileNotFoundError:
        return {
            "passed": False,
            "skipped": True,
            "reason": "npm_not_found",
        }
    output = (completed.stdout or "") + (completed.stderr or "")
    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "output_tail": output[-2000:],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the adversarial + regression production gate"
    )
    parser.add_argument(
        "--skip-slow",
        action="store_true",
        help="Skip the item-12 real-document PDF eval",
    )
    parser.add_argument(
        "--frontend",
        action="store_true",
        help="Also run citation Vitest files when frontend/node_modules exists",
    )
    parser.add_argument(
        "--out",
        default=str(RESULTS_PATH),
    )
    args = parser.parse_args(argv)

    python_report = run_python_pack(skip_slow=args.skip_slow)
    frontend_report = run_frontend_pack() if args.frontend else None

    passed = bool(python_report["passed"])
    if frontend_report is not None and not frontend_report.get("skipped"):
        passed = passed and bool(frontend_report.get("passed"))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "python": python_report,
        "frontend": frontend_report,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        "Adversarial gate: "
        + ("PASS" if passed else "FAIL")
        + f"  python {python_report['ok']}/{python_report['tests_run']}"
    )
    if python_report["failures"]:
        print("Failures:")
        for row in python_report["failures"]:
            print(f"  {row['id']}: {row['message']}")
    print(f"Written: {out_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
