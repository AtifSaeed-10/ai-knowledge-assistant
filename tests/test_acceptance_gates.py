"""Item 14 — production acceptance gates and release certificates."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from evaluation.acceptance_gates import (
    DEFAULT_THRESHOLDS,
    PROFILE_CI,
    PROFILE_RELEASE,
    evaluate_certificate,
    probe_rerank_zero_result,
    summarize_eval,
)
from evaluation.run_acceptance_gates import main


def _adv(*, passed: bool = True, ran: int = 186, ok: int | None = None) -> dict:
    ok_count = ran if (passed and ok is None) else (ok if ok is not None else ran - 1)
    return {
        "passed": passed,
        "python": {
            "passed": passed,
            "tests_run": ran,
            "ok": ok_count,
            "failed": 0 if passed else 1,
            "errors": 0,
        },
    }


def _row(**overrides) -> dict:
    row = {
        "skipped": False,
        "localized": True,
        "wrong_page": False,
        "false_precise": False,
        "ui_dropout": False,
        "unsupported_claim": False,
        "retrieval_hit": True,
        "content_type": "native_text",
    }
    row.update(overrides)
    return row


def _eval_report(rows: list[dict]) -> dict:
    return {"cases": rows, "evaluated": len(rows)}


def _passing_eval(*, count: int = 20) -> dict:
    return _eval_report([_row() for _ in range(count)])


class TestSummarizeEval(unittest.TestCase):
    def test_counts_only_non_skipped_rows(self):
        summary = summarize_eval(
            _eval_report(
                [
                    _row(),
                    _row(skipped=True),
                    _row(content_type="figure_caption", localized=True, retrieval_hit=None),
                ]
            )
        )
        self.assertEqual(summary["evaluated"], 2)
        self.assertEqual(summary["native_evaluated"], 1)
        self.assertEqual(summary["retrieval_evaluated"], 1)

    def test_empty_report_has_zero_volume(self):
        summary = summarize_eval({"evaluated": 20, "wrong_page_rate": 0.0, "cases": []})
        self.assertEqual(summary["evaluated"], 0)
        self.assertIsNone(summary["wrong_page_rate"])


class TestCertificatePolicy(unittest.TestCase):
    def test_ci_passes_without_held_out_pdfs(self):
        cert = evaluate_certificate(
            profile=PROFILE_CI,
            adversarial=_adv(),
            rerank_zero_result_rate=0.0,
            instability_rate=0.0,
        )
        self.assertTrue(cert["certified"])
        self.assertFalse(cert["human_signoff_required"])
        self.assertEqual(cert["blockers"], [])

    def test_ci_fails_when_adversarial_pack_fails(self):
        cert = evaluate_certificate(
            profile=PROFILE_CI,
            adversarial=_adv(passed=False, ok=180),
            rerank_zero_result_rate=0.0,
            instability_rate=1.0,
        )
        self.assertFalse(cert["certified"])
        self.assertIn("adversarial_pack", cert["blockers"])

    def test_release_does_not_certify_empty_held_out_catalog(self):
        cert = evaluate_certificate(
            profile=PROFILE_RELEASE,
            adversarial=_adv(),
            eval_report={"cases": [], "evaluated": 0},
            rerank_zero_result_rate=0.0,
            instability_rate=0.0,
        )
        self.assertFalse(cert["certified"])
        self.assertTrue(cert["human_signoff_required"])
        self.assertIn("held_out_evaluated", cert["blockers"])
        self.assertIn("localization_native", cert["blockers"])
        ids = {gate["id"]: gate for gate in cert["gates"]}
        self.assertIsNone(ids["wrong_page"]["actual"])
        self.assertFalse(ids["wrong_page"]["passed"])

    def test_release_passes_when_held_out_meets_bars(self):
        cert = evaluate_certificate(
            profile=PROFILE_RELEASE,
            adversarial=_adv(),
            eval_report=_passing_eval(count=20),
            rerank_zero_result_rate=0.0,
            instability_rate=0.0,
        )
        self.assertTrue(cert["certified"], cert["blockers"])
        self.assertEqual(cert["blockers"], [])

    def test_localization_below_bar_fails_release(self):
        rows = [_row(localized=False) for _ in range(2)] + [_row() for _ in range(18)]
        cert = evaluate_certificate(
            profile=PROFILE_RELEASE,
            adversarial=_adv(),
            eval_report=_eval_report(rows),
            rerank_zero_result_rate=0.0,
            instability_rate=0.0,
        )
        self.assertFalse(cert["certified"])
        self.assertIn("localization_native", cert["blockers"])

    def test_wrong_page_and_false_precise_caps(self):
        rows = [_row(wrong_page=True, false_precise=True)] + [_row() for _ in range(19)]
        cert = evaluate_certificate(
            profile=PROFILE_RELEASE,
            adversarial=_adv(),
            eval_report=_eval_report(rows),
            rerank_zero_result_rate=0.0,
            instability_rate=0.0,
        )
        self.assertIn("wrong_page", cert["blockers"])
        self.assertIn("false_precise", cert["blockers"])

    def test_native_ui_dropout_must_be_zero(self):
        rows = [_row(ui_dropout=True)] + [_row() for _ in range(19)]
        cert = evaluate_certificate(
            profile=PROFILE_RELEASE,
            adversarial=_adv(),
            eval_report=_eval_report(rows),
            rerank_zero_result_rate=0.0,
            instability_rate=0.0,
        )
        self.assertIn("ui_dropout_native", cert["blockers"])

    def test_retrieval_hit_below_recall_bar_fails(self):
        rows = [_row(retrieval_hit=False) for _ in range(2)] + [_row() for _ in range(18)]
        cert = evaluate_certificate(
            profile=PROFILE_RELEASE,
            adversarial=_adv(),
            eval_report=_eval_report(rows),
            rerank_zero_result_rate=0.0,
            instability_rate=0.0,
        )
        self.assertIn("retrieval_hit", cert["blockers"])

    def test_missing_adversarial_fails_required_gate(self):
        cert = evaluate_certificate(
            profile=PROFILE_CI,
            adversarial=None,
            rerank_zero_result_rate=0.0,
            instability_rate=0.0,
        )
        self.assertFalse(cert["certified"])
        self.assertIn("adversarial_pack", cert["blockers"])

    def test_frozen_thresholds_match_launch_bars(self):
        self.assertEqual(DEFAULT_THRESHOLDS.retrieval_hit_rate, 0.92)
        self.assertEqual(DEFAULT_THRESHOLDS.context_recall_rate, 0.90)
        self.assertEqual(DEFAULT_THRESHOLDS.grounding_rate, 0.90)
        self.assertEqual(DEFAULT_THRESHOLDS.localization_rate, 0.95)
        self.assertEqual(DEFAULT_THRESHOLDS.wrong_page_rate_max, 0.02)
        self.assertEqual(DEFAULT_THRESHOLDS.false_precise_rate_max, 0.01)
        self.assertEqual(DEFAULT_THRESHOLDS.ui_dropout_rate_max, 0.0)
        self.assertEqual(DEFAULT_THRESHOLDS.rerank_zero_result_rate_max, 0.0)
        self.assertEqual(DEFAULT_THRESHOLDS.instability_rate_max, 0.05)
        self.assertEqual(DEFAULT_THRESHOLDS.release_min_evaluated, 20)


class TestRerankProbe(unittest.TestCase):
    def test_nonempty_fused_pool_keeps_llm_slots(self):
        self.assertEqual(probe_rerank_zero_result(), 0.0)


class TestAcceptanceCli(unittest.TestCase):
    def test_ci_profile_certifies_from_saved_adversarial_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            adv_path = os.path.join(tmp, "adv.json")
            out_path = os.path.join(tmp, "cert.json")
            Path(adv_path).write_text(json.dumps(_adv()), encoding="utf-8")
            code = main(
                [
                    "--profile",
                    "ci",
                    "--adversarial-report",
                    adv_path,
                    "--skip-eval",
                    "--out",
                    out_path,
                ]
            )
            self.assertEqual(code, 0)
            cert = json.loads(Path(out_path).read_text(encoding="utf-8"))
        self.assertTrue(cert["certified"])
        self.assertEqual(cert["profile"], "ci")

    def test_release_profile_fails_closed_without_held_out_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            adv_path = os.path.join(tmp, "adv.json")
            out_path = os.path.join(tmp, "cert.json")
            Path(adv_path).write_text(json.dumps(_adv()), encoding="utf-8")
            code = main(
                [
                    "--profile",
                    "release",
                    "--adversarial-report",
                    adv_path,
                    "--skip-eval",
                    "--out",
                    out_path,
                ]
            )
            self.assertEqual(code, 1)
            cert = json.loads(Path(out_path).read_text(encoding="utf-8"))
        self.assertFalse(cert["certified"])
        self.assertIn("held_out_evaluated", cert["blockers"])

    def test_release_profile_certifies_when_eval_report_clears_bars(self):
        with tempfile.TemporaryDirectory() as tmp:
            adv_path = os.path.join(tmp, "adv.json")
            eval_path = os.path.join(tmp, "eval.json")
            out_path = os.path.join(tmp, "cert.json")
            Path(adv_path).write_text(json.dumps(_adv()), encoding="utf-8")
            Path(eval_path).write_text(json.dumps(_passing_eval(count=20)), encoding="utf-8")
            code = main(
                [
                    "--profile",
                    "release",
                    "--adversarial-report",
                    adv_path,
                    "--eval-report",
                    eval_path,
                    "--skip-eval",
                    "--out",
                    out_path,
                ]
            )
            self.assertEqual(code, 0)
            cert = json.loads(Path(out_path).read_text(encoding="utf-8"))
        self.assertTrue(cert["certified"])


if __name__ == "__main__":
    unittest.main()
