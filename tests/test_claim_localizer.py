"""Tests for claim → source-span → PDF region localization."""

from __future__ import annotations

import unittest

from claim_localizer import (
    STATUS_EXACT,
    STATUS_SEMANTIC_SPAN,
    STATUS_SENTENCE,
    STATUS_UNRESOLVED,
    STATUS_UNSUPPORTED,
    extract_claim_near_marker,
    is_informative_claim,
    localize_claim_in_chunk,
    score_text_support,
    token_f1,
)
from evidence_mapping import SOURCE_NATIVE, PageLayout, Span
from pdf_extraction import PRIMARY_ENGINE


def _layout(plain: str, spans: list[Span], page_number: int = 1) -> PageLayout:
    return PageLayout(
        page_number=page_number,
        width=612.0,
        height=792.0,
        plain=plain,
        spans=spans,
        source=SOURCE_NATIVE,
        engine=PRIMARY_ENGINE,
    )


class TestClaimExtraction(unittest.TestCase):
    def test_extracts_sentence_without_marker(self):
        answer = "Supervised learning uses labels.[E1] It is common in ML."
        claim = extract_claim_near_marker(answer, "E1")
        self.assertEqual(claim, "Supervised learning uses labels")

    def test_extracts_with_quoted_marker(self):
        answer = 'Uses labeled data.[E1:"labeled examples"]'
        claim = extract_claim_near_marker(answer, "E1")
        self.assertEqual(claim, "Uses labeled data")

    def test_strips_other_markers_from_claim(self):
        answer = (
            'Uses labels.[E1:"Labeled examples."] Also tasks.'
            '[E2:"Classification and regression."]'
        )
        claim = extract_claim_near_marker(answer, "E2")
        self.assertEqual(claim, "Also tasks")
        self.assertNotIn("Labeled", claim)


class TestTokenSimilarity(unittest.TestCase):
    def test_paraphrase_scores_higher_than_unrelated(self):
        claim = "learning from labeled training data"
        related = "Supervised learning uses labeled examples for training."
        unrelated = "Football rules govern offside decisions."
        self.assertGreater(token_f1(claim, related), token_f1(claim, unrelated))


class TestLocalizeClaimInChunk(unittest.TestCase):
    def setUp(self):
        self.chunk = (
            "Introduction to machine learning. Supervised learning uses labeled examples. "
            "Unsupervised learning finds hidden structure. Neural networks use layers."
        )
        self.spans = [
            Span("Supervised", (10.0, 10.0, 70.0, 22.0), (10.0, 10.0, 70.0, 22.0)),
            Span("learning", (72.0, 10.0, 120.0, 22.0), (72.0, 10.0, 120.0, 22.0)),
            Span("uses", (122.0, 10.0, 150.0, 22.0), (122.0, 10.0, 150.0, 22.0)),
            Span("labeled", (152.0, 10.0, 200.0, 22.0), (152.0, 10.0, 200.0, 22.0)),
            Span("examples.", (202.0, 10.0, 260.0, 22.0), (202.0, 10.0, 260.0, 22.0)),
        ]
        self.layouts = {1: _layout(self.chunk, self.spans)}

    def test_exact_quote_path(self):
        result = localize_claim_in_chunk(
            "Supervised learning uses labeled examples.",
            self.chunk,
            quote="labeled examples",
            layouts=self.layouts,
            page_start=1,
            page_end=1,
        )
        self.assertEqual(result.localization_status, STATUS_EXACT)
        self.assertTrue(result.quote_highlight_available)
        self.assertGreater(len(result.quote_regions), 0)

    def test_paraphrase_claim_localizes_to_sentence(self):
        result = localize_claim_in_chunk(
            "Supervised learning relies on labeled training data.",
            self.chunk,
            layouts=self.layouts,
            page_start=1,
            page_end=1,
        )
        self.assertIn(result.localization_status, {STATUS_SENTENCE, STATUS_SEMANTIC_SPAN})
        self.assertTrue(result.quote_highlight_available)
        self.assertIn("Supervised learning", " ".join(result.source_spans))

    def test_unrelated_claim_stays_unresolved(self):
        result = localize_claim_in_chunk(
            "Quantum entanglement enables teleportation.",
            self.chunk,
            layouts=self.layouts,
            page_start=1,
            page_end=1,
        )
        self.assertEqual(result.localization_status, STATUS_UNRESOLVED)
        self.assertFalse(result.quote_highlight_available)

    def test_without_layouts_keeps_source_span_without_pretending_boxes(self):
        result = localize_claim_in_chunk(
            "Supervised learning relies on labeled training data.",
            self.chunk,
            layouts={},
            page_start=1,
            page_end=1,
        )
        self.assertIn(result.localization_status, {STATUS_SENTENCE, STATUS_SEMANTIC_SPAN})
        self.assertFalse(result.quote_highlight_available)
        self.assertEqual(result.quote_regions, [])
        self.assertTrue(result.source_spans)
        self.assertIn("Supervised learning", " ".join(result.source_spans))

    def test_partial_claim_prefers_small_span(self):
        result = localize_claim_in_chunk(
            "uses labeled examples",
            self.chunk,
            layouts=self.layouts,
            page_start=1,
            page_end=1,
        )
        self.assertIn(result.localization_status, {STATUS_SEMANTIC_SPAN, STATUS_EXACT, STATUS_SENTENCE})
        self.assertTrue(result.quote_highlight_available)
        joined = " ".join(result.source_spans).lower()
        self.assertIn("labeled", joined)
        self.assertLess(len(joined), len(self.chunk) * 0.6)


class TestTextSupportScoring(unittest.TestCase):
    def test_supporting_passage_outscores_related_passage(self):
        claim = "Employment may be terminated with thirty days written notice."
        supporting = (
            "Either party may terminate employment by providing thirty days "
            "written notice to the other party."
        )
        related = (
            "This handbook also describes holiday pay, remote work eligibility, "
            "and the annual review cycle used by the company."
        )
        support_hit = score_text_support(claim, supporting)
        support_miss = score_text_support(claim, related)
        self.assertIn(support_hit.status, {STATUS_SENTENCE, STATUS_EXACT})
        self.assertGreater(support_hit.coverage, support_miss.coverage)
        self.assertGreater(support_hit.confidence, support_miss.confidence)

    def test_quote_containment_is_exact(self):
        chunk = "The policy requires written notice from either party."
        result = score_text_support(
            "The policy requires written notice.",
            chunk,
            quote="written notice",
        )
        self.assertEqual(result.status, STATUS_EXACT)
        self.assertEqual(result.confidence, 1.0)

    def test_unrelated_quote_does_not_count_as_exact_support(self):
        result = score_text_support(
            "Employment may be terminated with thirty days written notice.",
            "This handbook describes holiday pay and remote work.",
            quote="holiday pay",
        )
        self.assertNotEqual(result.status, STATUS_EXACT)

    def test_unrelated_chunk_is_unsupported(self):
        result = score_text_support(
            "Photosynthesis converts light energy into chemical energy.",
            "The stadium hosted the championship final in July.",
        )
        self.assertEqual(result.status, STATUS_UNSUPPORTED)

    def test_short_claim_is_not_informative(self):
        self.assertFalse(is_informative_claim("Uses labels."))
        self.assertTrue(
            is_informative_claim(
                "Employment may be terminated with thirty days written notice."
            )
        )


if __name__ == "__main__":
    unittest.main()
