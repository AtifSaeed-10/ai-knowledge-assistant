"""Item 15 — launch audit policy and failure-injection probes."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from evaluation.launch_audit import (
    PRODUCTION_SCENARIOS,
    evaluate_launch_audit,
    failure_injection_probes,
    probe_empty_allowlist_drops_hits,
    probe_ghost_document_isolation,
    probe_invented_marker_stripped,
    probe_super_focused_empty_aborts,
)


def _passing_kwargs(**overrides):
    base = dict(
        release_certified=True,
        held_out_evaluated=20,
        scenario_hits=9,
        scenario_total=9,
        qx3_stable=True,
        p95_latency_ms=1200.0,
        failure_probes=failure_injection_probes(),
        human_signoff=False,
    )
    base.update(overrides)
    return base


class TestProductionScenarioCatalog(unittest.TestCase):
    def test_nine_generic_scenarios(self):
        self.assertEqual(len(PRODUCTION_SCENARIOS), 9)
        ids = [row["id"] for row in PRODUCTION_SCENARIOS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("definitional_fact", ids)
        self.assertIn("dedication_front_matter", ids)
        self.assertIn("article_number", ids)


class TestFailureInjection(unittest.TestCase):
    def test_ghost_document_does_not_search_corpus(self):
        with patch(
            "evaluation.launch_audit.resolve_retrieval_scope",
            return_value=([], False),
        ):
            result = probe_ghost_document_isolation()
        self.assertTrue(result.passed)

    def test_super_focused_empty_aborts(self):
        result = probe_super_focused_empty_aborts()
        self.assertTrue(result.passed)

    def test_empty_allowlist_drops_hits(self):
        result = probe_empty_allowlist_drops_hits()
        self.assertTrue(result.passed)

    def test_invented_marker_stripped(self):
        result = probe_invented_marker_stripped()
        self.assertTrue(result.passed, result.extra)

    def test_pack_all_pass(self):
        probes = failure_injection_probes()
        self.assertEqual(len(probes), 4)
        self.assertTrue(all(item.passed for item in probes))


class TestLaunchAuditPolicy(unittest.TestCase):
    def test_engineering_pass_without_signoff_is_not_launch_approved(self):
        report = evaluate_launch_audit(**_passing_kwargs())
        self.assertTrue(report["engineering_passed"])
        self.assertFalse(report["launch_approved"])
        self.assertIn("human_signoff_required", report["blockers"])

    def test_signoff_approves_when_engineering_passes(self):
        report = evaluate_launch_audit(**_passing_kwargs(human_signoff=True))
        self.assertTrue(report["engineering_passed"])
        self.assertTrue(report["launch_approved"])
        self.assertEqual(report["blockers"], [])

    def test_uncertified_release_blocks_engineering(self):
        report = evaluate_launch_audit(
            **_passing_kwargs(release_certified=False, human_signoff=True)
        )
        self.assertFalse(report["engineering_passed"])
        self.assertFalse(report["launch_approved"])
        self.assertIn("release_not_certified", report["blockers"])

    def test_item_15_is_not_a_substitute_for_held_out_volume(self):
        report = evaluate_launch_audit(
            **_passing_kwargs(held_out_evaluated=0, human_signoff=True)
        )
        self.assertFalse(report["engineering_passed"])
        self.assertIn("held_out_replay_short", report["blockers"])

    def test_scenario_miss_blocks(self):
        report = evaluate_launch_audit(
            **_passing_kwargs(scenario_hits=8, human_signoff=True)
        )
        self.assertFalse(report["engineering_passed"])
        self.assertIn("production_scenarios", report["blockers"])


if __name__ == "__main__":
    unittest.main()
