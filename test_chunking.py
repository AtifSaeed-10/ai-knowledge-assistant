"""Deterministic tests for RAG V2 Phase 1 chunking helpers."""

from __future__ import annotations

import unittest

from chunking import (
    MIN_CHUNK_CHARS,
    PAGE_JOIN,
    build_chunks_from_pages,
    build_document_text,
    build_section_ranges,
    chroma_metadata_for_chunk,
    is_heading_line,
    merge_tiny_chunks,
    pages_for_span,
    slugify_section,
)


class TestPageSpanMapping(unittest.TestCase):
    def test_build_document_text_offsets(self):
        pages = [
            {"page_number": 1, "text": "AAA"},
            {"page_number": 2, "text": "BBBB"},
            {"page_number": 3, "text": "CC"},
        ]
        full_text, spans = build_document_text(pages)
        self.assertEqual(full_text, "AAA" + PAGE_JOIN + "BBBB" + PAGE_JOIN + "CC")
        self.assertEqual(spans[0], (0, 3, 1))
        self.assertEqual(spans[1], (3 + len(PAGE_JOIN), 3 + len(PAGE_JOIN) + 4, 2))
        self.assertEqual(
            spans[2],
            (
                3 + len(PAGE_JOIN) + 4 + len(PAGE_JOIN),
                3 + len(PAGE_JOIN) + 4 + len(PAGE_JOIN) + 2,
                3,
            ),
        )

    def test_skips_empty_pages(self):
        pages = [
            {"page_number": 1, "text": "Hello"},
            {"page_number": 2, "text": "   "},
            {"page_number": 3, "text": "World"},
        ]
        full_text, spans = build_document_text(pages)
        self.assertEqual(full_text, "Hello" + PAGE_JOIN + "World")
        self.assertEqual([s[2] for s in spans], [1, 3])

    def test_pages_for_span_single_page(self):
        _, spans = build_document_text(
            [
                {"page_number": 5, "text": "abcdefghij"},
                {"page_number": 6, "text": "klmnop"},
            ]
        )
        # First page only
        self.assertEqual(pages_for_span(0, 5, spans), (5, 5))

    def test_pages_for_span_cross_page(self):
        full_text, spans = build_document_text(
            [
                {"page_number": 10, "text": "AAAAAAAAAA"},
                {"page_number": 11, "text": "BBBBBBBBBB"},
            ]
        )
        # Span covering end of page 10 and start of page 11
        join_at = full_text.index(PAGE_JOIN)
        start = join_at - 3
        end = join_at + len(PAGE_JOIN) + 3
        self.assertEqual(pages_for_span(start, end, spans), (10, 11))


class TestTinyChunkMerging(unittest.TestCase):
    def test_merge_tiny_into_previous(self):
        chunks = [
            {
                "text": "A" * 250,
                "page_start": 1,
                "page_end": 1,
                "page_number": 1,
                "section_title": "Intro",
                "section_id": "intro",
                "parent_id": "intro",
                "char_count": 250,
            },
            {
                "text": "tiny",
                "page_start": 2,
                "page_end": 2,
                "page_number": 2,
                "section_title": "Other",
                "section_id": "other",
                "parent_id": "other",
                "char_count": 4,
            },
        ]
        merged = merge_tiny_chunks(chunks, min_chars=MIN_CHUNK_CHARS)
        self.assertEqual(len(merged), 1)
        self.assertIn("tiny", merged[0]["text"])
        self.assertEqual(merged[0]["page_start"], 1)
        self.assertEqual(merged[0]["page_end"], 2)
        self.assertEqual(merged[0]["section_title"], "Intro")

    def test_merge_leading_tiny_forward(self):
        chunks = [
            {
                "text": "x",
                "page_start": 1,
                "page_end": 1,
                "page_number": 1,
                "section_title": "Lead",
                "section_id": "lead",
                "parent_id": "lead",
                "char_count": 1,
            },
            {
                "text": "B" * 250,
                "page_start": 2,
                "page_end": 2,
                "page_number": 2,
                "section_title": "",
                "section_id": "",
                "parent_id": "",
                "char_count": 250,
            },
        ]
        merged = merge_tiny_chunks(chunks, min_chars=MIN_CHUNK_CHARS)
        self.assertEqual(len(merged), 1)
        self.assertTrue(merged[0]["text"].startswith("x"))
        self.assertEqual(merged[0]["page_start"], 1)
        self.assertEqual(merged[0]["page_end"], 2)
        self.assertEqual(merged[0]["section_title"], "Lead")

    def test_keeps_large_chunks(self):
        chunks = [
            {
                "text": "A" * 300,
                "page_start": 1,
                "page_end": 1,
                "page_number": 1,
                "section_title": "",
                "section_id": "",
                "parent_id": "",
                "char_count": 300,
            },
            {
                "text": "B" * 300,
                "page_start": 2,
                "page_end": 2,
                "page_number": 2,
                "section_title": "",
                "section_id": "",
                "parent_id": "",
                "char_count": 300,
            },
        ]
        merged = merge_tiny_chunks(chunks, min_chars=MIN_CHUNK_CHARS)
        self.assertEqual(len(merged), 2)


class TestHeadingsAndBuildChunks(unittest.TestCase):
    def test_heading_detection(self):
        self.assertTrue(is_heading_line("UNIT I"))
        self.assertTrue(is_heading_line("1.2 Components of Learning"))
        self.assertTrue(is_heading_line("INTRODUCTION TO CLUSTERING"))
        self.assertFalse(is_heading_line("This is a normal sentence about learning."))
        self.assertFalse(is_heading_line("a"))

    def test_slugify(self):
        self.assertEqual(slugify_section("1.2 Components of Learning"), "1-2-components-of-learning")

    def test_section_ranges(self):
        text = (
            "Preamble text.\n"
            "1.1 What Is Machine Learning?\n"
            "Body of section one.\n"
            "1.2 Components of Learning\n"
            "Body of section two."
        )
        ranges = build_section_ranges(text)
        titles = [r[2] for r in ranges if r[2]]
        self.assertIn("1.1 What Is Machine Learning?", titles)
        self.assertIn("1.2 Components of Learning", titles)

    def test_build_chunks_metadata_and_neighbors(self):
        pages = [
            {
                "page_number": 1,
                "text": (
                    "1.1 What Is Machine Learning?\n"
                    + ("Machine learning uses data. " * 40)
                ),
            },
            {
                "page_number": 2,
                "text": (
                    "1.2 Components of Learning\n"
                    + ("Storage abstraction generalization. " * 40)
                ),
            },
        ]
        chunks = build_chunks_from_pages(
            pages,
            document_id="doc-test",
            chunk_size=400,
            chunk_overlap=50,
            min_chunk_chars=50,
        )
        self.assertGreater(len(chunks), 1)

        first = chunks[0]
        last = chunks[-1]
        self.assertEqual(first["prev_chunk_id"], "")
        self.assertEqual(first["chunk_id"], "doc-test_0")
        self.assertEqual(first["next_chunk_id"], "doc-test_1")
        self.assertEqual(last["next_chunk_id"], "")
        self.assertEqual(last["prev_chunk_id"], f"doc-test_{len(chunks) - 2}")

        # Citation-compatible page_number equals page_start
        for c in chunks:
            self.assertEqual(c["page_number"], c["page_start"])
            self.assertGreaterEqual(c["page_end"], c["page_start"])
            self.assertIn(c["page_start"], (1, 2))

        # At least one chunk should pick up a heading section
        section_titles = {c["section_title"] for c in chunks}
        self.assertTrue(
            any("Machine Learning" in t or "Components" in t for t in section_titles)
        )

        meta = chroma_metadata_for_chunk(first, "doc-test", "sample.pdf")
        self.assertEqual(meta["document_id"], "doc-test")
        self.assertEqual(meta["filename"], "sample.pdf")
        self.assertIn("page_start", meta)
        self.assertIn("prev_chunk_id", meta)
        self.assertIsInstance(meta["char_count"], int)

    def test_empty_pages_yield_no_chunks(self):
        chunks = build_chunks_from_pages(
            [{"page_number": 1, "text": "   "}],
            document_id="empty",
        )
        self.assertEqual(chunks, [])


if __name__ == "__main__":
    unittest.main()
