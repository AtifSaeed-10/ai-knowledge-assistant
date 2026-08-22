"""Phase 1 evidence provenance: mapping, PAGE_JOIN recovery, persistence."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pymupdf as fitz

from chunking import PAGE_JOIN, build_chunks_from_pages
from database.db import init_db
from database.document_store import create_document, delete_document, get_document
from database.evidence_store import (
    get_chunk_evidence,
    list_chunk_evidence,
    list_page_layouts,
    replace_document_evidence,
)
from evidence_mapping import (
    SOURCE_NATIVE,
    SOURCE_NONE,
    PageLayout,
    Span,
    build_document_evidence,
    compact,
    locate_chunk_slices,
    make_snippet,
    map_chunk_to_evidence,
    map_quote_to_regions,
    map_slice_to_spans,
)
from pdf_extraction import PRIMARY_ENGINE, extract_pages_from_pdf


def _write_text_pdf(path: str, page_texts: list[str]) -> None:
    doc = fitz.open()
    try:
        for text in page_texts:
            page = doc.new_page()
            page.insert_text((72, 72), text)
        doc.save(path)
    finally:
        doc.close()


def _layout(plain: str, spans: list[Span], page_number: int = 1) -> PageLayout:
    return PageLayout(
        page_number=page_number,
        width=612.0,
        height=792.0,
        plain=plain,
        spans=spans,
        source=SOURCE_NATIVE if spans else SOURCE_NONE,
        engine=PRIMARY_ENGINE,
    )


class TestCompactAndSnippet(unittest.TestCase):
    def test_compact_drops_whitespace_keeps_letters(self):
        text, orig = compact("Hello\n  World")
        self.assertEqual(text, "HelloWorld")
        self.assertEqual(len(orig), len(text))

    def test_compact_optional_hyphen_drop(self):
        kept, _ = compact("learn-\ning")
        dropped, _ = compact("learn-\ning", drop_hyphens=True)
        self.assertEqual(kept, "learn-ing")
        self.assertEqual(dropped, "learning")

    def test_snippet_collapses_whitespace(self):
        snippet = make_snippet("Supervised   learning\nis labeled.")
        self.assertEqual(snippet, "Supervised learning is labeled.")


class TestWhitespaceNormalizedMapping(unittest.TestCase):
    def test_newlines_in_plain_map_to_span_boxes(self):
        plain = "Hello\nWorld"
        spans = [
            Span("Hello", (10.0, 10.0, 50.0, 20.0), (10.0, 10.0, 50.0, 20.0)),
            Span("World", (10.0, 22.0, 55.0, 32.0), (10.0, 22.0, 55.0, 32.0)),
        ]
        mapped = map_slice_to_spans(plain, spans, plain)
        self.assertEqual(mapped["match_type"], "normalized")
        self.assertEqual(mapped["bbox_count"], 2)
        self.assertEqual(len(mapped["regions"]), 2)

    def test_exact_span_concat_substring(self):
        spans = [
            Span("Hello World", (1.0, 1.0, 80.0, 12.0), (1.0, 1.0, 80.0, 12.0)),
        ]
        mapped = map_slice_to_spans("Hello World", spans, "Hello World")
        self.assertEqual(mapped["match_type"], "exact")
        self.assertEqual(mapped["bbox_count"], 1)


class TestLocateAndJoinRecovery(unittest.TestCase):
    def test_contiguous_chunk_is_not_join_recovered(self):
        full_text = "ABCDEFGHIJ leftover"
        page_spans = [(0, len(full_text), 1)]
        slices, _, recovered, fully = locate_chunk_slices(
            full_text, full_text, page_spans, 0
        )
        self.assertFalse(recovered)
        self.assertTrue(fully)
        self.assertEqual(len(slices), 1)
        self.assertEqual(slices[0]["page"], 1)

    def test_page_join_merged_chunk_is_recovered(self):
        full_text = "ABCDEFGHIJ leftover"
        page_spans = [(0, len(full_text), 1)]
        chunk_text = "ABCDEFGHIJ" + PAGE_JOIN + "leftover"
        self.assertEqual(full_text.find(chunk_text), -1)
        slices, _, recovered, fully = locate_chunk_slices(
            chunk_text, full_text, page_spans, 0
        )
        self.assertTrue(recovered)
        self.assertTrue(fully)
        self.assertEqual([row["text"] for row in slices], ["ABCDEFGHIJ", "leftover"])

    def test_unlocatable_chunk_is_not_fully_located(self):
        slices, _, recovered, fully = locate_chunk_slices(
            "not in the document at all",
            "ABCDEF",
            [(0, 6, 1)],
            0,
        )
        self.assertTrue(recovered)
        self.assertFalse(fully)
        self.assertEqual(slices, [])


class TestMultiPageAndFailures(unittest.TestCase):
    def test_multi_page_chunk_maps_both_pages(self):
        join = PAGE_JOIN
        full_text = "AAAA" + join + "BBBB"
        page_spans = [
            (0, 4, 1),
            (4 + len(join), 4 + len(join) + 4, 2),
        ]
        layouts = {
            1: _layout(
                "AAAA",
                [Span("AAAA", (10.0, 10.0, 40.0, 20.0), (10.0, 10.0, 40.0, 20.0))],
                1,
            ),
            2: _layout(
                "BBBB",
                [Span("BBBB", (10.0, 40.0, 40.0, 50.0), (10.0, 40.0, 40.0, 50.0))],
                2,
            ),
        }
        chunk = {
            "text": full_text,
            "chunk_id": "doc_0",
            "page_start": 1,
            "page_end": 2,
        }
        record, _ = map_chunk_to_evidence(
            chunk,
            document_id="doc",
            full_text=full_text,
            page_spans=page_spans,
            layouts=layouts,
            search_from=0,
            text_engine=PRIMARY_ENGINE,
        )
        self.assertTrue(record["highlight_available"])
        self.assertEqual(record["page_start"], 1)
        self.assertEqual(record["page_end"], 2)
        pages = {region["page"] for region in record["regions"]}
        self.assertEqual(pages, {1, 2})
        for region in record["regions"]:
            self.assertEqual(region["coord_space"], "pdf")
            self.assertLess(region["x0"], region["x1"])

    def test_mapping_failure_does_not_invent_boxes(self):
        full_text = "Visible text on the page"
        page_spans = [(0, len(full_text), 1)]
        layouts = {
            1: _layout(full_text, [], 1),
        }
        chunk = {
            "text": full_text,
            "chunk_id": "doc_0",
            "page_start": 1,
            "page_end": 1,
        }
        record, _ = map_chunk_to_evidence(
            chunk,
            document_id="doc",
            full_text=full_text,
            page_spans=page_spans,
            layouts=layouts,
            search_from=0,
            text_engine=PRIMARY_ENGINE,
        )
        self.assertFalse(record["highlight_available"])
        self.assertEqual(record["regions"], [])
        self.assertEqual(record["match_type"], "failed")

    def test_join_recovered_chunk_gets_real_boxes(self):
        full_text = "ABCDEFGHIJ leftover"
        page_spans = [(0, len(full_text), 1)]
        spans = [
            Span(full_text, (12.0, 12.0, 200.0, 24.0), (12.0, 12.0, 200.0, 24.0)),
        ]
        layouts = {1: _layout(full_text, spans, 1)}
        chunk = {
            "text": "ABCDEFGHIJ" + PAGE_JOIN + "leftover",
            "chunk_id": "doc_0",
            "page_start": 1,
            "page_end": 1,
        }
        record, _ = map_chunk_to_evidence(
            chunk,
            document_id="doc",
            full_text=full_text,
            page_spans=page_spans,
            layouts=layouts,
            search_from=0,
            text_engine=PRIMARY_ENGINE,
        )
        self.assertTrue(record["join_recovered"])
        self.assertTrue(record["highlight_available"])
        self.assertGreaterEqual(len(record["regions"]), 1)
        self.assertEqual(record["regions"][0]["coord_space"], "pdf")


class TestNativePdfIntegration(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_native_text_pdf_chunks_have_highlight_regions(self):
        path = os.path.join(self.tmp, "native.pdf")
        _write_text_pdf(
            path,
            [
                "Supervised learning is a machine-learning approach where a model "
                "learns from labeled examples. It can be used for classification.",
                "Unsupervised learning finds structure in unlabeled data. "
                "Clustering and dimensionality reduction are common methods.",
            ],
        )
        extraction = extract_pages_from_pdf(path)
        chunks = build_chunks_from_pages(extraction.pages, "native-doc")
        self.assertGreaterEqual(len(chunks), 1)
        evidence = build_document_evidence(
            path,
            "native-doc",
            extraction.pages,
            chunks,
            text_engine=extraction.engine_used,
        )
        self.assertEqual(len(evidence["chunks"]), len(chunks))
        self.assertEqual(len(evidence["pages"]), 2)
        highlighted = [row for row in evidence["chunks"] if row["highlight_available"]]
        self.assertEqual(len(highlighted), len(chunks))
        first = highlighted[0]
        self.assertGreaterEqual(len(first["regions"]), 1)
        self.assertIn(first["match_type"], {"exact", "normalized", "fuzzy_compact"})
        self.assertEqual(first["source"], SOURCE_NATIVE)
        self.assertLessEqual(first["page_start"], first["page_end"])
        pages = {region["page"] for region in first["regions"]}
        self.assertTrue(pages <= {1, 2})
        segments = first.get("segments") or []
        self.assertGreaterEqual(len(segments), 1)
        self.assertTrue(any(row.get("highlight_available") for row in segments))

    def test_multi_page_native_pdf_chunk(self):
        path = os.path.join(self.tmp, "two-page.pdf")
        _write_text_pdf(
            path,
            [
                "Supervised learning uses labeled examples.",
                "Unsupervised learning uses unlabeled examples.",
            ],
        )
        extraction = extract_pages_from_pdf(path)
        chunks = build_chunks_from_pages(extraction.pages, "two-page")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["page_start"], 1)
        self.assertEqual(chunks[0]["page_end"], 2)
        evidence = build_document_evidence(
            path,
            "two-page",
            extraction.pages,
            chunks,
            text_engine=extraction.engine_used,
        )
        record = evidence["chunks"][0]
        self.assertTrue(record["highlight_available"])
        self.assertEqual({region["page"] for region in record["regions"]}, {1, 2})


class TestEvidencePersistence(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, "evidence.db")
        self._db_patch = patch("database.db.SQLITE_DB_PATH", self.db_path)
        self._db_patch.start()
        init_db()

    def tearDown(self):
        self._db_patch.stop()
        self._tmpdir.cleanup()

    def test_replace_get_and_delete_evidence(self):
        document_id = create_document("sample.pdf")
        evidence = {
            "pages": [
                {
                    "page_number": 1,
                    "width": 612.0,
                    "height": 792.0,
                    "source": SOURCE_NATIVE,
                    "engine": PRIMARY_ENGINE,
                    "span_count": 2,
                }
            ],
            "chunks": [
                {
                    "chunk_id": f"{document_id}_0",
                    "document_id": document_id,
                    "page_start": 1,
                    "page_end": 1,
                    "snippet": "Supervised learning uses labeled examples.",
                    "highlight_available": True,
                    "match_type": "normalized",
                    "source": SOURCE_NATIVE,
                    "text_engine": PRIMARY_ENGINE,
                    "layout_engine": PRIMARY_ENGINE,
                    "join_recovered": False,
                    "ranges": [{"page": 1, "char_start": 0, "char_end": 20, "match_type": "normalized"}],
                    "regions": [
                        {
                            "page": 1,
                            "x0": 10.0,
                            "y0": 10.0,
                            "x1": 80.0,
                            "y1": 22.0,
                            "coord_space": "pdf",
                        }
                    ],
                }
            ],
        }
        replace_document_evidence(document_id, evidence)

        loaded = get_chunk_evidence(f"{document_id}_0")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertTrue(loaded["highlight_available"])
        self.assertEqual(loaded["snippet"], "Supervised learning uses labeled examples.")
        self.assertEqual(len(loaded["regions"]), 1)
        self.assertEqual(loaded["regions"][0]["page"], 1)
        self.assertEqual(len(list_page_layouts(document_id)), 1)
        self.assertEqual(len(list_chunk_evidence(document_id)), 1)

        self.assertTrue(delete_document(document_id))
        self.assertIsNone(get_chunk_evidence(f"{document_id}_0"))
        self.assertEqual(list_page_layouts(document_id), [])
        self.assertIsNone(get_document(document_id))

    @patch("indexer.chromadb.PersistentClient")
    @patch("indexer.model")
    def test_index_pdf_persists_evidence_without_changing_ready_status(
        self, mock_model, mock_client
    ):
        from indexer import index_pdf

        pdf_path = os.path.join(self._tmpdir.name, "ready.pdf")
        long_page = ("Matter is made of particles. " * 25).strip()
        _write_text_pdf(pdf_path, [long_page, long_page])
        document_id = create_document("ready.pdf")

        mock_collection = MagicMock()
        mock_client.return_value.get_or_create_collection.return_value = mock_collection
        mock_model.embed.return_value = [[0.01] * 384]

        index_pdf(pdf_path, document_id)

        record = get_document(document_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["status"], "ready")
        self.assertGreater(record["total_chunks"], 0)
        mock_collection.add.assert_called()
        mock_model.embed.assert_called()

        stored = list_chunk_evidence(document_id)
        self.assertEqual(len(stored), record["total_chunks"])
        self.assertTrue(any(item["highlight_available"] for item in stored))
        self.assertTrue(all(item["layout_engine"] == PRIMARY_ENGINE for item in stored))
        layouts = list_page_layouts(document_id)
        self.assertEqual(len(layouts), 2)

        metadata = mock_collection.add.call_args.kwargs["metadatas"]
        first_meta = metadata[0]
        self.assertNotIn("regions", first_meta)
        self.assertNotIn("highlight_available", first_meta)
        self.assertIn("document_id", first_meta)
        self.assertIn("page_start", first_meta)


class TestChunkingUnchanged(unittest.TestCase):
    def test_chunk_dict_keys_remain_citation_compatible(self):
        pages = [
            {"page_number": 1, "text": "Machine Learning is a field of AI. " * 40},
            {"page_number": 2, "text": "Components of a learning system include data. " * 40},
        ]
        chunks = build_chunks_from_pages(pages, "doc-test")
        self.assertGreater(len(chunks), 0)
        required = {
            "text",
            "page_number",
            "page_start",
            "page_end",
            "chunk_id",
            "chunk_index",
            "char_count",
        }
        for chunk in chunks:
            self.assertTrue(required.issubset(chunk.keys()))
            self.assertNotIn("regions", chunk)
            self.assertNotIn("highlight_available", chunk)


class TestQuoteMapping(unittest.TestCase):
    def setUp(self):
        self.plain = (
            "Intro padding. Supervised learning uses labeled examples. "
            "Later, unsupervised learning finds hidden structure."
        )
        self.intro = Span(
            "Intro padding. ",
            (10.0, 10.0, 80.0, 22.0),
            (10.0, 10.0, 80.0, 22.0),
        )
        self.supervised = Span(
            "Supervised learning uses labeled examples.",
            (10.0, 24.0, 220.0, 36.0),
            (10.0, 24.0, 220.0, 36.0),
        )
        self.later = Span(
            " Later, ",
            (10.0, 40.0, 60.0, 52.0),
            (10.0, 40.0, 60.0, 52.0),
        )
        self.unsupervised = Span(
            "unsupervised learning finds hidden structure.",
            (10.0, 56.0, 240.0, 68.0),
            (10.0, 56.0, 240.0, 68.0),
        )
        self.layouts = {
            1: _layout(
                self.plain,
                [self.intro, self.supervised, self.later, self.unsupervised],
                1,
            )
        }

    def _map(self, quote: str, **kwargs):
        return map_quote_to_regions(
            quote,
            chunk_text=kwargs.get("chunk_text", self.plain),
            layouts=kwargs.get("layouts", self.layouts),
            page_start=1,
            page_end=1,
            ranges=kwargs.get("ranges"),
        )

    def test_valid_quote_returns_only_quote_regions(self):
        mapped = self._map("Supervised learning uses labeled examples.")
        self.assertTrue(mapped["quote_highlight_available"])
        self.assertEqual(len(mapped["regions"]), 1)
        region = mapped["regions"][0]
        self.assertEqual(region["y0"], 24.0)
        self.assertEqual(region["y1"], 36.0)
        self.assertEqual(region["coord_space"], "pdf")

    def test_quote_spanning_multiple_spans_returns_each_box(self):
        mapped = self._map("labeled examples. Later")
        self.assertTrue(mapped["quote_highlight_available"])
        self.assertEqual(len(mapped["regions"]), 2)
        ys = sorted(item["y0"] for item in mapped["regions"])
        self.assertEqual(ys, [24.0, 40.0])

    def test_quote_spanning_lines_returns_line_boxes(self):
        plain = "Supervised learning\nuses labeled examples."
        layouts = {
            1: _layout(
                plain,
                [
                    Span(
                        "Supervised learning",
                        (10.0, 10.0, 140.0, 22.0),
                        (10.0, 10.0, 140.0, 22.0),
                    ),
                    Span(
                        "uses labeled examples.",
                        (10.0, 26.0, 180.0, 38.0),
                        (10.0, 26.0, 180.0, 38.0),
                    ),
                ],
                1,
            )
        }
        mapped = self._map(
            "Supervised learning uses labeled examples.",
            chunk_text=plain,
            layouts=layouts,
        )
        self.assertTrue(mapped["quote_highlight_available"])
        self.assertEqual(len(mapped["regions"]), 2)
        self.assertEqual(
            sorted(item["y0"] for item in mapped["regions"]),
            [10.0, 26.0],
        )

    def test_missing_quote_does_not_invent_boxes(self):
        mapped = self._map("this sentence does not appear in the chunk")
        self.assertFalse(mapped["quote_highlight_available"])
        self.assertEqual(mapped["regions"], [])

    def test_same_chunk_different_quotes_get_distinct_regions(self):
        first = self._map("Supervised learning uses labeled examples.")
        second = self._map("unsupervised learning finds hidden structure.")
        self.assertTrue(first["quote_highlight_available"])
        self.assertTrue(second["quote_highlight_available"])
        self.assertEqual(first["regions"][0]["y0"], 24.0)
        self.assertEqual(second["regions"][0]["y0"], 56.0)
        self.assertNotEqual(first["regions"], second["regions"])


if __name__ == "__main__":
    unittest.main()
