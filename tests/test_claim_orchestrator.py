"""Item 5 — claim-centric orchestration over the recall pool."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from claim_orchestrator import (
    orchestrate_all_claims,
    orchestrate_claim_for_evidence,
)
from claim_validator import finalize_answer_citations


TERMINATION_CLAIM = (
    "Employment may be terminated with thirty days written notice."
)
TERMINATION_CHUNK = (
    "Either party may terminate employment by providing thirty days written "
    "notice to the other party. Notice must be delivered in writing."
)
HOLIDAY_CHUNK = (
    "This employee handbook also describes holiday pay, remote work eligibility, "
    "and the annual review cycle used by the company."
)
PHOTOSYNTHESIS_CLAIM = (
    "Photosynthesis converts light energy into chemical energy in chloroplasts."
)
PHOTOSYNTHESIS_CHUNK = (
    "Photosynthesis converts light energy into chemical energy stored in glucose "
    "inside chloroplasts of plant cells."
)
RESPIRATION_CHUNK = (
    "Cellular respiration in mitochondria produces ATP by oxidizing glucose "
    "and other organic molecules."
)


def _source(
    *,
    evidence_id: str,
    chunk_id: str,
    page: int,
    relevance: int,
    document_id: str = "doc-policy",
    filename: str = "handbook.pdf",
    text: str = "",
    citation_eligible: bool = True,
) -> dict:
    row = {
        "evidence_id": evidence_id,
        "chunk_id": chunk_id,
        "document_id": document_id,
        "filename": filename,
        "page": page,
        "relevance": relevance,
        "snippet": text[:80],
        "citation_eligible": citation_eligible,
    }
    if text:
        row["text"] = text
    return row


def _fake_resolve(**kwargs):
    return {
        "chunk_id": kwargs["chunk_id"],
        "quote_mapping_status": "sentence",
        "quote_highlight_available": False,
        "quote_regions": [],
        "localization_confidence": 0.72,
        "source_spans": ["thirty days written notice"],
        "source": "",
        "page_start": None,
        "highlight_available": False,
        "text_engine": "",
    }


class TestOrchestrateClaimForEvidence(unittest.TestCase):
    def setUp(self):
        self.bound = _source(
            evidence_id="E1",
            chunk_id="policy_0",
            page=2,
            relevance=100,
            text=HOLIDAY_CHUNK,
        )
        self.recall = [
            self.bound,
            _source(
                evidence_id=None,
                chunk_id="policy_3",
                page=18,
                relevance=48,
                text=TERMINATION_CHUNK,
                citation_eligible=False,
            ),
        ]

    def test_rebinds_e1_to_supporting_recall_chunk(self):
        result = orchestrate_claim_for_evidence(
            "E1",
            self.bound,
            self.recall,
            claim_text=TERMINATION_CLAIM,
            quote=None,
            pdf_path=None,
            localize=False,
        )
        self.assertTrue(result.rebinding_applied)
        self.assertEqual(result.retrieval_chunk_id, "policy_0")
        self.assertEqual(result.selected_chunk_id, "policy_3")
        self.assertEqual(result.source["chunk_id"], "policy_3")
        self.assertEqual(result.source["page"], 18)
        self.assertEqual(result.source["evidence_id"], "E1")
        self.assertEqual(result.support_status, "supported")
        self.assertGreater(result.support_confidence, 0.4)
        self.assertGreaterEqual(len(result.candidates_searched), 2)
        self.assertNotIn("text", result.source)

    def test_does_not_rebind_across_documents(self):
        other_doc = _source(
            evidence_id=None,
            chunk_id="other_1",
            page=4,
            relevance=40,
            document_id="doc-other",
            filename="other.pdf",
            text=TERMINATION_CHUNK,
            citation_eligible=False,
        )
        result = orchestrate_claim_for_evidence(
            "E1",
            self.bound,
            [self.bound, other_doc],
            claim_text=TERMINATION_CLAIM,
            quote=None,
            pdf_path=None,
            localize=False,
        )
        self.assertFalse(result.rebinding_applied)
        self.assertEqual(result.selected_chunk_id, "policy_0")

    def test_close_scores_do_not_hop(self):
        near = _source(
            evidence_id="E2",
            chunk_id="policy_1",
            page=3,
            relevance=90,
            text=HOLIDAY_CHUNK + " Reviews occur each January.",
        )
        result = orchestrate_claim_for_evidence(
            "E1",
            self.bound,
            [self.bound, near],
            claim_text="The handbook describes holiday pay and remote work.",
            quote=None,
            pdf_path=None,
            localize=False,
        )
        self.assertFalse(result.rebinding_applied)
        self.assertEqual(result.selected_chunk_id, "policy_0")

    def test_short_claim_does_not_rebind(self):
        result = orchestrate_claim_for_evidence(
            "E1",
            self.bound,
            self.recall,
            claim_text="Uses labels.",
            quote=None,
            pdf_path=None,
            localize=False,
        )
        self.assertFalse(result.rebinding_applied)
        self.assertEqual(result.selected_chunk_id, "policy_0")

    def test_independent_claims_bind_separately(self):
        photo = _source(
            evidence_id="E1",
            chunk_id="bio_0",
            page=1,
            relevance=97,
            document_id="doc-bio",
            filename="biology.pdf",
            text=RESPIRATION_CHUNK,
        )
        light = _source(
            evidence_id="E2",
            chunk_id="bio_2",
            page=6,
            relevance=88,
            document_id="doc-bio",
            filename="biology.pdf",
            text=PHOTOSYNTHESIS_CHUNK,
        )
        pool = [photo, light]
        first = orchestrate_claim_for_evidence(
            "E1",
            photo,
            pool,
            claim_text=PHOTOSYNTHESIS_CLAIM,
            quote=None,
            pdf_path=None,
            localize=False,
        )
        second = orchestrate_claim_for_evidence(
            "E2",
            light,
            pool,
            claim_text=PHOTOSYNTHESIS_CLAIM,
            quote=None,
            pdf_path=None,
            localize=False,
        )
        self.assertTrue(first.rebinding_applied)
        self.assertEqual(first.selected_chunk_id, "bio_2")
        self.assertFalse(second.rebinding_applied)
        self.assertEqual(second.selected_chunk_id, "bio_2")

    @patch("claim_orchestrator.resolve_claim_evidence", side_effect=_fake_resolve)
    def test_localizes_only_the_winning_chunk(self, resolve):
        result = orchestrate_claim_for_evidence(
            "E1",
            self.bound,
            self.recall,
            claim_text=TERMINATION_CLAIM,
            quote=None,
            pdf_path=None,
            localize=True,
        )
        self.assertTrue(result.rebinding_applied)
        self.assertEqual(resolve.call_count, 1)
        self.assertEqual(resolve.call_args.kwargs["chunk_id"], "policy_3")
        self.assertEqual(result.source["quote_mapping_status"], "sentence")


class TestOrchestrateAllClaims(unittest.TestCase):
    def test_searches_recall_pool_not_only_citeable_slots(self):
        bound = _source(
            evidence_id="E1",
            chunk_id="policy_0",
            page=2,
            relevance=100,
            text=HOLIDAY_CHUNK,
        )
        recall = [
            bound,
            _source(
                evidence_id=None,
                chunk_id="policy_3",
                page=18,
                relevance=48,
                text=TERMINATION_CHUNK,
                citation_eligible=False,
            ),
        ]
        answer = f"{TERMINATION_CLAIM} [E1]"
        enriched, meta = orchestrate_all_claims(
            answer,
            [bound],
            claim_texts={"E1": TERMINATION_CLAIM},
            quotes_by_id={},
            pdf_cache={},
            resolve_regions=False,
            recall_candidates=recall,
        )
        self.assertEqual(enriched[0]["chunk_id"], "policy_3")
        self.assertEqual(enriched[0]["page"], 18)
        self.assertTrue(meta["E1"]["rebinding_applied"])
        self.assertEqual(meta["E1"]["support_status"], "supported")
        searched_ids = {row["chunk_id"] for row in meta["E1"]["candidates_searched"]}
        self.assertIn("policy_3", searched_ids)
        self.assertIn("policy_0", searched_ids)

    def test_drops_quote_that_does_not_match_rebound_chunk(self):
        bound = _source(
            evidence_id="E1",
            chunk_id="policy_0",
            page=2,
            relevance=100,
            text=HOLIDAY_CHUNK,
        )
        recall = [
            bound,
            _source(
                evidence_id=None,
                chunk_id="policy_3",
                page=18,
                relevance=48,
                text=TERMINATION_CHUNK,
                citation_eligible=False,
            ),
        ]
        enriched, _meta = orchestrate_all_claims(
            'Employment may be terminated with thirty days written notice.[E1:"holiday pay"]',
            [{**bound, "quotes": ["holiday pay"], "quote": "holiday pay"}],
            claim_texts={"E1": TERMINATION_CLAIM},
            quotes_by_id={"E1": ["holiday pay"]},
            pdf_cache={},
            resolve_regions=False,
            recall_candidates=recall,
        )
        self.assertEqual(enriched[0]["chunk_id"], "policy_3")
        self.assertIsNone(enriched[0].get("quote"))
        self.assertEqual(enriched[0].get("quotes") or [], [])


class TestFinalizeUsesRecallPool(unittest.TestCase):
    @patch("claim_orchestrator.resolve_claim_evidence", side_effect=_fake_resolve)
    @patch("claim_validator._chunk_text_for_source")
    def test_finalize_rebinds_and_strips_stale_quote(self, chunk_text, _resolve):
        bound = _source(
            evidence_id="E1",
            chunk_id="policy_0",
            page=2,
            relevance=100,
            text=HOLIDAY_CHUNK,
        )
        recall = [
            bound,
            _source(
                evidence_id=None,
                chunk_id="policy_3",
                page=18,
                relevance=48,
                text=TERMINATION_CHUNK,
                citation_eligible=False,
            ),
        ]
        chunk_text.side_effect = lambda source: {
            "policy_0": HOLIDAY_CHUNK,
            "policy_3": TERMINATION_CHUNK,
        }.get(str(source.get("chunk_id")), "")

        answer = (
            'Employment may be terminated with thirty days written notice.'
            '[E1:"holiday pay"]'
        )
        finalized, enriched = finalize_answer_citations(
            answer,
            [bound],
            resolve_regions=True,
            recall_candidates=recall,
        )
        self.assertEqual(enriched[0]["chunk_id"], "policy_3")
        self.assertEqual(enriched[0]["page"], 18)
        self.assertIn("[E1]", finalized)
        self.assertNotIn("holiday pay", finalized)
        self.assertEqual(enriched[0]["support_status"], "supported")


if __name__ == "__main__":
    unittest.main()
