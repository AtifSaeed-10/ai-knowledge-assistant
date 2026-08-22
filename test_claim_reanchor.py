"""Item 6 — cross-chunk / cross-page evidence re-anchoring."""

from __future__ import annotations

import unittest

from claim_localizer import STATUS_SENTENCE, STATUS_SEMANTIC_SPAN, STATUS_EXACT
from claim_reanchor import (
    ReanchorWindow,
    join_overlapping,
    neighbor_chunk_ids,
    owner_chunk_id,
    reanchor_claim,
    stitch_windows,
)
from evidence_mapping import SOURCE_NATIVE, PageLayout, Span
from evidence_trace import ui_status_for_source
from pdf_extraction import PRIMARY_ENGINE


def _layout(plain: str, spans: list[Span], page_number: int) -> PageLayout:
    return PageLayout(
        page_number=page_number,
        width=612.0,
        height=792.0,
        plain=plain,
        spans=spans,
        source=SOURCE_NATIVE,
        engine=PRIMARY_ENGINE,
    )


class TestJoinOverlapping(unittest.TestCase):
    def test_drops_duplicated_overlap(self):
        left = "Either party may terminate employment by providing thirty days written notice"
        right = "thirty days written notice to the other party."
        joined = join_overlapping(left, right)
        self.assertEqual(joined.count("thirty days written notice"), 1)
        self.assertIn("other party", joined)

    def test_concatenates_when_no_overlap(self):
        joined = join_overlapping("The board may terminate the agreement with", "thirty days notice.")
        self.assertIn("agreement with thirty days notice.", joined)


class TestStitchAndOwner(unittest.TestCase):
    def test_owner_is_chunk_with_majority_of_span(self):
        windows = [
            ReanchorWindow(chunk_id="doc_4", text="AAA BBB CCC ", page_start=1, page_end=1),
            ReanchorWindow(chunk_id="doc_5", text="DDD EEE FFF", page_start=1, page_end=1),
        ]
        stitched, spans = stitch_windows(windows)
        self.assertEqual(stitched, "AAA BBB CCC DDD EEE FFF")
        owner = owner_chunk_id(0, 11, spans, "doc_4")
        self.assertEqual(owner, "doc_4")
        owner_tail = owner_chunk_id(12, 23, spans, "doc_4")
        self.assertEqual(owner_tail, "doc_5")

    def test_neighbor_ids_are_prev_and_next_only(self):
        ids = neighbor_chunk_ids(
            {"prev_chunk_id": "doc_3", "next_chunk_id": "doc_5"},
            radius=1,
        )
        self.assertEqual(ids, ["doc_3", "doc_5"])
        self.assertEqual(neighbor_chunk_ids({"prev_chunk_id": "doc_3"}, radius=0), [])


class TestReanchorClaim(unittest.TestCase):
    def test_split_sentence_rebinds_to_neighbor_chunk(self):
        left = "The board may terminate the agreement with "
        right = "thirty days written notice to the other party."
        claim = "The board may terminate the agreement with thirty days written notice."
        left_spans = [
            Span("The", (10, 10, 30, 22), (10, 10, 30, 22)),
            Span("board", (32, 10, 70, 22), (32, 10, 70, 22)),
            Span("may", (72, 10, 96, 22), (72, 10, 96, 22)),
            Span("terminate", (98, 10, 160, 22), (98, 10, 160, 22)),
            Span("the", (162, 10, 184, 22), (162, 10, 184, 22)),
            Span("agreement", (186, 10, 250, 22), (186, 10, 250, 22)),
            Span("with", (252, 10, 280, 22), (252, 10, 280, 22)),
        ]
        right_spans = [
            Span("thirty", (10, 40, 50, 52), (10, 40, 50, 52)),
            Span("days", (52, 40, 80, 52), (52, 40, 80, 52)),
            Span("written", (82, 40, 130, 52), (82, 40, 130, 52)),
            Span("notice", (132, 40, 180, 52), (132, 40, 180, 52)),
            Span("to", (182, 40, 198, 52), (182, 40, 198, 52)),
            Span("the", (200, 40, 220, 52), (200, 40, 220, 52)),
            Span("other", (222, 40, 258, 52), (222, 40, 258, 52)),
            Span("party.", (260, 40, 300, 52), (260, 40, 300, 52)),
        ]
        layouts = {
            10: _layout(left + right, left_spans + right_spans, 10),
        }
        primary = ReanchorWindow(
            chunk_id="policy_4",
            document_id="doc-policy",
            text=left,
            page_start=10,
            page_end=10,
            page_number=10,
        )
        neighbor = ReanchorWindow(
            chunk_id="policy_5",
            document_id="doc-policy",
            text=right,
            page_start=10,
            page_end=10,
            page_number=10,
        )
        result = reanchor_claim(
            claim,
            None,
            [primary, neighbor],
            primary_chunk_id="policy_4",
            layouts=layouts,
        )
        self.assertTrue(result.stitched)
        joined_span = " ".join(result.source_spans).lower()
        self.assertTrue(
            ("terminate" in joined_span and "notice" in joined_span)
            or result.localization.quote_highlight_available
        )
        self.assertTrue(result.localization.quote_highlight_available)
        self.assertGreater(len(result.localization.quote_regions), 0)
        self.assertLessEqual(len(result.localization.quote_regions), 12)
        # Completing the split sentence should land on the neighbor that holds
        # "thirty days written notice", not stay on the truncated lead-in.
        self.assertEqual(result.chunk_id, "policy_5")
        self.assertTrue(result.cross_chunk)

    def test_cross_page_chunk_updates_page_to_supporting_region(self):
        page1 = "Holiday pay and remote work occupy this opening page of the handbook."
        page2 = "Either party may terminate employment by providing thirty days written notice."
        claim = "Employment may be terminated with thirty days written notice."
        spans_p2 = [
            Span("Either", (10, 200, 50, 212), (10, 200, 50, 212)),
            Span("party", (52, 200, 90, 212), (52, 200, 90, 212)),
            Span("may", (92, 200, 116, 212), (92, 200, 116, 212)),
            Span("terminate", (118, 200, 180, 212), (118, 200, 180, 212)),
            Span("employment", (182, 200, 250, 212), (182, 200, 250, 212)),
            Span("by", (252, 200, 268, 212), (252, 200, 268, 212)),
            Span("providing", (270, 200, 330, 212), (270, 200, 330, 212)),
            Span("thirty", (332, 200, 372, 212), (332, 200, 372, 212)),
            Span("days", (374, 200, 400, 212), (374, 200, 400, 212)),
            Span("written", (402, 200, 450, 212), (402, 200, 450, 212)),
            Span("notice.", (452, 200, 500, 212), (452, 200, 500, 212)),
        ]
        layouts = {
            18: _layout(page1, [Span("Holiday", (10, 10, 70, 22), (10, 10, 70, 22))], 18),
            19: _layout(page2, spans_p2, 19),
        }
        window = ReanchorWindow(
            chunk_id="policy_8",
            document_id="doc-policy",
            text=page1 + " " + page2,
            page_start=18,
            page_end=19,
            page_number=18,
        )
        result = reanchor_claim(
            claim,
            None,
            [window],
            primary_chunk_id="policy_8",
            layouts=layouts,
        )
        self.assertEqual(result.chunk_id, "policy_8")
        self.assertTrue(result.cross_page)
        self.assertEqual(result.page, 19)
        self.assertEqual(result.localization.page_start, 19)
        self.assertTrue(result.localization.quote_highlight_available)
        pages = {int(r["page"]) for r in result.localization.quote_regions}
        self.assertEqual(pages, {19})

    def test_does_not_use_unrelated_neighbor(self):
        primary_text = (
            "Photosynthesis converts light energy into chemical energy stored in glucose "
            "inside chloroplasts of plant cells."
        )
        neighbor_text = "Cellular respiration in mitochondria produces ATP from glucose."
        claim = "Photosynthesis converts light energy into chemical energy in chloroplasts."
        photo_spans = [
            Span("Photosynthesis", (10, 10, 90, 22), (10, 10, 90, 22)),
            Span("converts", (92, 10, 140, 22), (92, 10, 140, 22)),
            Span("light", (142, 10, 170, 22), (142, 10, 170, 22)),
            Span("energy", (172, 10, 210, 22), (172, 10, 210, 22)),
            Span("into", (212, 10, 236, 22), (212, 10, 236, 22)),
            Span("chemical", (238, 10, 290, 22), (238, 10, 290, 22)),
            Span("energy", (292, 10, 330, 22), (292, 10, 330, 22)),
            Span("stored", (332, 10, 370, 22), (332, 10, 370, 22)),
            Span("in", (372, 10, 386, 22), (372, 10, 386, 22)),
            Span("glucose", (388, 10, 430, 22), (388, 10, 430, 22)),
        ]
        layouts = {3: _layout(primary_text, photo_spans, 3)}
        primary = ReanchorWindow(
            chunk_id="bio_2",
            text=primary_text,
            page_start=3,
            page_end=3,
            page_number=3,
        )
        other = ReanchorWindow(
            chunk_id="bio_3",
            text=neighbor_text,
            page_start=4,
            page_end=4,
            page_number=4,
        )
        result = reanchor_claim(
            claim,
            None,
            [primary, other],
            primary_chunk_id="bio_2",
            layouts=layouts,
        )
        self.assertEqual(result.chunk_id, "bio_2")
        self.assertFalse(result.cross_chunk)
        self.assertIn(result.localization.localization_status, {STATUS_SENTENCE, STATUS_SEMANTIC_SPAN, STATUS_EXACT})


class TestUiStatusWithoutBoxes(unittest.TestCase):
    def test_sentence_without_highlight_is_snippet_only(self):
        status = ui_status_for_source(
            {
                "quote_mapping_status": "sentence",
                "quote_highlight_available": False,
            }
        )
        self.assertEqual(status, "snippet_only")

    def test_sentence_with_highlight_is_ok(self):
        status = ui_status_for_source(
            {
                "quote_mapping_status": "sentence",
                "quote_highlight_available": True,
            }
        )
        self.assertEqual(status, "highlight_ok")


if __name__ == "__main__":
    unittest.main()
