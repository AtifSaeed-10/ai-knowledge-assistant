"""Tests for evidence_trace observability."""

from __future__ import annotations

import unittest

from evidence_trace import (
    _markers_in_answer,
    attach_trace_dict_to_sources,
    build_evidence_trace,
    log_evidence_trace,
    snapshot_recall_candidates,
    snapshot_retrieval_candidates,
    ui_status_for_source,
)


class EvidenceTraceTests(unittest.TestCase):
    def test_markers_in_answer_order(self):
        answer = "First [E2] then [E1] again [E2]."
        self.assertEqual(_markers_in_answer(answer), ["E2", "E1"])

    def test_trace_records_rebind_from_orchestrator_keys(self):
        retrieved = [
            {
                "evidence_id": "E1",
                "chunk_id": "c1",
                "document_id": "d1",
                "page": 5,
                "relevance": 80,
                "citation_eligible": True,
                "evidence_state": "citeable",
            }
        ]
        enriched = [
            {
                "evidence_id": "E1",
                "chunk_id": "c2",
                "document_id": "d1",
                "page": 26,
                "quote_mapping_status": "sentence",
                "quote_highlight_available": True,
                "quote_regions": [
                    {
                        "page": 26,
                        "x0": 0,
                        "y0": 0,
                        "x1": 1,
                        "y1": 1,
                        "coord_space": "pdf",
                    }
                ],
                "localization_confidence": 0.7,
                "support_status": "supported",
                "content_type": "native_text",
            }
        ]
        answer = "The event happened on page 26 [E1]."
        trace = build_evidence_trace(
            answer,
            retrieved,
            enriched,
            enriched,
            claim_texts={"E1": "The event happened on page 26"},
            orchestration_meta={
                "E1": {
                    "retrieval_chunk_id": "c1",
                    "selected_chunk_id": "c2",
                    "rebinding_applied": True,
                    "candidates_searched": [
                        {
                            "chunk_id": "c1",
                            "score": 0.4,
                            "text": "must never appear in the trace",
                        },
                        {"chunk_id": "c2", "score": 0.9, "status": "supported"},
                    ],
                }
            },
        )
        self.assertTrue(trace.trace_id)
        self.assertEqual(len(trace.claims), 1)
        claim = trace.claims[0]
        self.assertTrue(claim.rebinding_applied)
        self.assertEqual(claim.retrieval_chunk_id, "c1")
        self.assertEqual(claim.selected_chunk_id, "c2")
        self.assertEqual(claim.localization_status, "sentence")
        self.assertEqual(claim.highlight_pages, [26])
        self.assertEqual(claim.ui_status, "highlight_ok")
        self.assertEqual(trace.markers_missing_citation, [])
        self.assertEqual(len(claim.candidates_searched), 2)
        self.assertNotIn("text", claim.candidates_searched[0])
        self.assertEqual(claim.candidates_searched[0]["chunk_id"], "c1")

    def test_trace_reads_legacy_orchestrator_aliases(self):
        retrieved = [{"evidence_id": "E1", "chunk_id": "old", "page": 2}]
        enriched = [
            {
                "evidence_id": "E1",
                "chunk_id": "new",
                "page": 9,
                "quote_mapping_status": "sentence",
                "quote_highlight_available": False,
            }
        ]
        trace = build_evidence_trace(
            "Claim [E1].",
            retrieved,
            enriched,
            enriched,
            orchestration_meta={
                "E1": {
                    "retrieval_chunk_id": "old",
                    "selected_chunk_id": "new",
                    "rebinding_applied": True,
                    "candidates_searched": [{"chunk_id": "new", "score": 1.0}],
                }
            },
        )
        claim = trace.claims[0]
        self.assertTrue(claim.rebinding_applied)
        self.assertEqual(claim.retrieval_chunk_id, "old")
        self.assertEqual(claim.selected_chunk_id, "new")
        self.assertEqual(claim.candidates_searched[0]["chunk_id"], "new")

    def test_dropped_marker_is_flagged(self):
        retrieved = [{"evidence_id": "E1", "chunk_id": "c1", "page": 3}]
        enriched = [
            {
                "evidence_id": "E1",
                "chunk_id": "c1",
                "page": 3,
                "quote_mapping_status": "sentence",
                "quote_highlight_available": False,
            }
        ]
        trace = build_evidence_trace(
            "A claim [E1].",
            retrieved,
            enriched,
            [],
        )
        self.assertEqual(trace.markers_missing_citation, ["E1"])
        self.assertEqual(trace.claims[0].ui_status, "citation_dropped")
        self.assertFalse(trace.claims[0].in_final_citations)

    def test_figure_and_scan_ui_status(self):
        figure = {
            "quote_highlight_available": False,
            "quote_mapping_status": "none",
            "content_type": "figure_caption",
        }
        scan = {
            "quote_highlight_available": False,
            "quote_mapping_status": "none",
            "content_type": "scanned_or_image",
        }
        self.assertEqual(ui_status_for_source(figure), "page_only_visual")
        self.assertEqual(ui_status_for_source(scan), "page_only_scan")
        self.assertEqual(
            ui_status_for_source(
                {
                    "quote_highlight_available": False,
                    "quote_mapping_status": "sentence",
                }
            ),
            "snippet_only",
        )
        self.assertEqual(
            ui_status_for_source(
                {
                    "quote_highlight_available": True,
                    "quote_mapping_status": "sentence",
                }
            ),
            "highlight_ok",
        )

    def test_snapshot_retrieval_candidates(self):
        rows = snapshot_retrieval_candidates(
            [
                {
                    "evidence_id": "E1",
                    "chunk_id": "a",
                    "document_id": "d",
                    "page": 1,
                    "relevance": 50,
                    "citation_eligible": True,
                    "evidence_state": "citeable",
                }
            ]
        )
        self.assertEqual(rows[0]["evidence_id"], "E1")
        self.assertTrue(rows[0]["citation_eligible"])
        self.assertEqual(rows[0]["evidence_state"], "citeable")

    def test_recall_snapshot_strips_passage_text(self):
        rows = snapshot_recall_candidates(
            [
                {
                    "chunk_id": "r1",
                    "page": 4,
                    "score": 0.8,
                    "text": "secret passage",
                    "snippet": "also secret",
                }
            ]
        )
        self.assertEqual(rows[0]["chunk_id"], "r1")
        self.assertNotIn("text", rows[0])
        self.assertNotIn("snippet", rows[0])

    def test_attach_trace_includes_correlation_id(self):
        retrieved = [{"evidence_id": "E1", "chunk_id": "c1", "page": 1}]
        enriched = [
            {
                "evidence_id": "E1",
                "chunk_id": "c1",
                "page": 1,
                "quote_mapping_status": "sentence",
                "quote_highlight_available": True,
                "quote_regions": [{"page": 1, "x0": 0, "y0": 0, "x1": 1, "y1": 1}],
            }
        ]
        trace = build_evidence_trace(
            "Hello [E1].",
            retrieved,
            enriched,
            enriched,
            recall_candidates=[{"chunk_id": "c1", "page": 1, "text": "nope"}],
        )
        attached = attach_trace_dict_to_sources(enriched, trace.to_dict())
        compact = attached[0]["evidence_trace"]
        self.assertEqual(compact["trace_id"], trace.trace_id)
        self.assertEqual(compact["selected_chunk_id"], "c1")
        self.assertNotIn("text", compact)
        self.assertEqual(len(trace.recall_candidates), 1)
        self.assertNotIn("text", trace.recall_candidates[0])

    def test_log_includes_trace_id_and_omits_passage_text(self):
        retrieved = [{"evidence_id": "E1", "chunk_id": "c1", "page": 1}]
        enriched = [
            {
                "evidence_id": "E1",
                "chunk_id": "c1",
                "page": 1,
                "quote_mapping_status": "sentence",
                "quote_highlight_available": False,
            }
        ]
        trace = build_evidence_trace(
            "Hello [E1].",
            retrieved,
            enriched,
            enriched,
            orchestration_meta={
                "E1": {
                    "candidates_searched": [
                        {"chunk_id": "c1", "text": "must not be logged"}
                    ]
                }
            },
        )
        with self.assertLogs("evidence_trace", level="INFO") as captured:
            log_evidence_trace(
                trace,
                conversation_id="conv-1",
                question="What happened on page 26?",
            )
        joined = " ".join(captured.output)
        self.assertIn(trace.trace_id, joined)
        self.assertIn("conv-1", joined)
        self.assertNotIn("must not be logged", joined)


if __name__ == "__main__":
    unittest.main()
