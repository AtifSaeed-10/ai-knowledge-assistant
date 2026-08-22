"""Tests for evidence_trace observability."""

import unittest

from evidence_trace import (
    build_evidence_trace,
    snapshot_retrieval_candidates,
    _markers_in_answer,
)


class EvidenceTraceTests(unittest.TestCase):
    def test_markers_in_answer_order(self):
        answer = "First [E2] then [E1] again [E2]."
        self.assertEqual(_markers_in_answer(answer), ["E2", "E1"])

    def test_trace_flags_dropout(self):
        retrieved = [
            {
                "evidence_id": "E1",
                "chunk_id": "c1",
                "document_id": "d1",
                "page": 5,
                "relevance": 80,
            }
        ]
        enriched = [
            {
                "evidence_id": "E1",
                "chunk_id": "c1",
                "document_id": "d1",
                "page": 26,
                "quote_mapping_status": "sentence",
                "quote_highlight_available": True,
                "quote_regions": [{"page": 26, "x0": 0, "y0": 0, "x1": 1, "y1": 1, "coord_space": "pdf"}],
                "localization_confidence": 0.7,
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
                    "candidates_searched": [{"chunk_id": "c2", "score": 0.9}],
                }
            },
        )
        self.assertEqual(len(trace.claims), 1)
        claim = trace.claims[0]
        self.assertTrue(claim.rebinding_applied)
        self.assertEqual(claim.localization_status, "sentence")
        self.assertEqual(claim.highlight_pages, [26])
        self.assertEqual(trace.markers_missing_citation, [])

    def test_snapshot_retrieval_candidates(self):
        rows = snapshot_retrieval_candidates(
            [{"evidence_id": "E1", "chunk_id": "a", "document_id": "d", "page": 1, "relevance": 50}]
        )
        self.assertEqual(rows[0]["evidence_id"], "E1")


if __name__ == "__main__":
    unittest.main()
