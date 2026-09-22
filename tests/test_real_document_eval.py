"""Item 12 — real-document evaluation harness."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf as fitz

from database.db import init_db
from database.document_store import create_document, delete_document
from evaluation.run_real_document_eval import (
    EvalCorpus,
    RealDocumentCase,
    find_chunk_containing,
    load_cases,
    main,
    prepare_eval_document,
    retrieval_hit,
    run_evaluation,
    score_case_result,
)


NOTICE = (
    "Either party may terminate employment by providing thirty days written "
    "notice to the other party."
)
FIGURE_CAPTION = "Figure 1. Pipeline overview of the encoding stage."
TABLE_CAPTION = "Table 1. Hyperparameters used in training."


def _wrap_lines(text: str, width: int = 88) -> list[str]:
    lines: list[str] = []
    for paragraph in re.split(r"\n+", text.strip()):
        words = paragraph.split()
        current: list[str] = []
        size = 0
        for word in words:
            extra = len(word) + (1 if current else 0)
            if current and size + extra > width:
                lines.append(" ".join(current))
                current = [word]
                size = len(word)
            else:
                current.append(word)
                size += extra
        if current:
            lines.append(" ".join(current))
    return lines


def _write_eval_pdf(path: str, page_texts: list[str]) -> None:
    doc = fitz.open()
    try:
        for text in page_texts:
            page = doc.new_page()
            y = 72.0
            for line in _wrap_lines(text):
                page.insert_text((72, y), line)
                y += 14.0
        doc.save(path)
    finally:
        doc.close()


def _native_page() -> str:
    extra = (
        "Employment agreements in this evaluation corpus specify how a contract may end. "
        "Notice must be delivered in writing to the registered office of the recipient. "
        "Unused paid leave is not part of the notice calculation and does not extend "
        "the termination date. Staff records in this corpus also describe remote work "
        "eligibility and the annual review cycle used by the company. "
    )
    return (NOTICE + " " + extra) * 3


def _figure_page() -> str:
    return (
        f"{FIGURE_CAPTION} "
        "Fig. 1 Schematic of the encoder used in the evaluation corpus for "
        "document ingestion. Illustration 1. System architecture for the "
        "encoding pipeline during retrieval evaluation."
    )


def _table_page() -> str:
    return (
        f"{TABLE_CAPTION} "
        "Table 1 lists the learning rate, batch size, and epoch counts compared "
        "in the study. | learning_rate | batch_size | epochs | | 0.001 | 32 | 10 | "
        "| 0.0005 | 16 | 20 | | 0.0001 | 8 | 30 |"
    )


def _case(**overrides) -> RealDocumentCase:
    base = dict(
        case_id="notice",
        document_id="doc-eval",
        claim_text=NOTICE,
        answer=f"{NOTICE} [E1]",
        expected_page=1,
        expected_pages=(1,),
        expected_quote_substring="thirty days written notice",
        content_type="native_text",
        evidence_id="E1",
    )
    base.update(overrides)
    return RealDocumentCase(**base)


def _cited(**overrides) -> dict:
    row = {
        "evidence_id": "E1",
        "chunk_id": "doc-eval_0",
        "quote_highlight_available": True,
        "quote_regions": [
            {
                "page": 1,
                "x0": 72.0,
                "y0": 72.0,
                "x1": 200.0,
                "y1": 84.0,
                "coord_space": "pdf",
            }
        ],
        "page": 1,
        "source_spans": ["thirty days written notice"],
        "quote": "thirty days written notice",
        "snippet": NOTICE,
        "content_type": "native_text",
        "ui_status": "highlighted",
        "quote_mapping_status": "sentence",
    }
    row.update(overrides)
    return row


class TestLoadCases(unittest.TestCase):
    def test_empty_file_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "empty.json")
            Path(path).write_text(json.dumps({"cases": []}), encoding="utf-8")
            self.assertEqual(load_cases(Path(path)), [])

    def test_default_catalog_has_held_out_volume(self):
        cases = load_cases(
            Path(__file__).resolve().parent / "evaluation" / "real_document_cases.json"
        )
        self.assertGreaterEqual(len(cases), 20)

    def test_chunk_id_is_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cases.json")
            Path(path).write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "case_id": "a",
                                "document_id": "doc-1",
                                "expected_page": 4,
                                "expected_quote_substring": "written notice",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            cases = load_cases(Path(path))
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].chunk_id, "")
        self.assertEqual(cases[0].expected_pages, (4,))
        self.assertEqual(cases[0].evidence_id, "E1")


class TestScoreCaseResult(unittest.TestCase):
    def test_native_localized(self):
        result = score_case_result(
            _case(),
            finalized_answer=f"{NOTICE} [E1]",
            visible=[_cited()],
        )
        self.assertTrue(result["localized"])
        self.assertTrue(result["highlight"])
        self.assertFalse(result["wrong_page"])
        self.assertFalse(result["false_precise"])
        self.assertFalse(result["ui_dropout"])
        self.assertFalse(result["unsupported_claim"])

    def test_wrong_page_is_false_precise_when_highlighted(self):
        result = score_case_result(
            _case(expected_page=3, expected_pages=(3,)),
            finalized_answer=f"{NOTICE} [E1]",
            visible=[_cited(page=1)],
        )
        self.assertTrue(result["wrong_page"])
        self.assertTrue(result["false_precise"])
        self.assertFalse(result["localized"])

    def test_ui_dropout_when_marker_has_no_visible_source(self):
        result = score_case_result(
            _case(),
            finalized_answer=f"{NOTICE} [E1]",
            visible=[],
        )
        self.assertTrue(result["ui_dropout"])
        self.assertTrue(result["marker_present"])
        self.assertFalse(result["localized"])

    def test_unsupported_when_marker_stripped(self):
        result = score_case_result(
            _case(),
            finalized_answer=NOTICE,
            visible=[],
        )
        self.assertTrue(result["unsupported_claim"])
        self.assertFalse(result["marker_present"])
        self.assertFalse(result["ui_dropout"])

    def test_figure_page_only_success_without_highlight(self):
        result = score_case_result(
            _case(
                case_id="figure",
                claim_text=FIGURE_CAPTION,
                answer=f"{FIGURE_CAPTION} [E1]",
                expected_page=2,
                expected_pages=(2,),
                expected_quote_substring="Pipeline overview",
                content_type="figure_caption",
            ),
            finalized_answer=f"{FIGURE_CAPTION} [E1]",
            visible=[
                _cited(
                    page=2,
                    quote_highlight_available=False,
                    quote_regions=[],
                    source_spans=[],
                    quote="",
                    snippet=FIGURE_CAPTION,
                    content_type="figure_caption",
                    ui_status="page_only",
                )
            ],
        )
        self.assertFalse(result["highlight"])
        self.assertFalse(result["false_precise"])
        self.assertTrue(result["localized"])
        self.assertTrue(result["page_only_success"])

    def test_retrieval_hit_by_substring(self):
        case = _case(chunk_id="", expected_chunk_id=None)
        self.assertTrue(
            retrieval_hit(
                case,
                [{"chunk_id": "other_0", "text": NOTICE, "page": 1}],
            )
        )
        self.assertFalse(
            retrieval_hit(
                case,
                [{"chunk_id": "other_0", "text": "unrelated catering policy", "page": 9}],
            )
        )


class TestRealDocumentEvalIntegration(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name
        self.db_path = os.path.join(self.tmp, "eval.db")
        self._db_patch = patch("database.db.SQLITE_DB_PATH", self.db_path)
        self._db_patch.start()
        init_db()
        self.pdf_path = os.path.join(self.tmp, "eval-corpus.pdf")
        _write_eval_pdf(
            self.pdf_path,
            [_native_page(), _figure_page(), _table_page()],
        )
        self.document_id = create_document("eval-corpus.pdf")
        self.corpus = prepare_eval_document(
            self.pdf_path,
            document_id=self.document_id,
        )

    def tearDown(self):
        try:
            delete_document(self.document_id)
        except Exception:
            pass
        self._db_patch.stop()
        self._tmpdir.cleanup()

    def _case_for(self, needle: str, **overrides) -> RealDocumentCase:
        chunk = find_chunk_containing(self.corpus.chunks, needle)
        self.assertIsNotNone(chunk, msg=f"no chunk contained {needle!r}")
        assert chunk is not None
        return _case(
            document_id=self.document_id,
            pdf_path=self.pdf_path,
            chunk_id=str(chunk["chunk_id"]),
            expected_chunk_id=str(chunk["chunk_id"]),
            **overrides,
        )

    def test_native_claim_localizes_to_page_one(self):
        case = self._case_for(
            "thirty days written notice",
            case_id="native-notice",
            claim_text=NOTICE,
            answer=f"{NOTICE} [E1]",
            expected_page=1,
            expected_pages=(1,),
            expected_quote_substring="thirty days written notice",
            content_type="native_text",
            question="How much notice is required to end employment?",
        )
        report = run_evaluation([case], corpus=self.corpus)
        self.assertEqual(report.evaluated, 1)
        row = report.cases[0]
        self.assertFalse(row.get("skipped"), row)
        self.assertTrue(row["marker_present"], row)
        self.assertFalse(row["ui_dropout"], row)
        self.assertFalse(row["wrong_page"], row)
        self.assertFalse(row["false_precise"], row)
        self.assertIn(1, row["pages"], row)
        self.assertTrue(row["localized"], row)
        self.assertTrue(row["highlight"], row)

    def test_figure_claim_lands_on_page_two(self):
        case = self._case_for(
            "Pipeline overview of the encoding stage",
            case_id="figure-caption",
            claim_text=FIGURE_CAPTION,
            answer=f"{FIGURE_CAPTION} [E1]",
            expected_page=2,
            expected_pages=(2,),
            expected_quote_substring="Pipeline overview",
            content_type="figure_caption",
        )
        report = run_evaluation([case], corpus=self.corpus)
        row = report.cases[0]
        self.assertFalse(row.get("skipped"), row)
        self.assertFalse(row["wrong_page"], row)
        self.assertFalse(row["false_precise"], row)
        self.assertIn(2, row["pages"], row)
        self.assertTrue(row["localized"] or row["page_only_success"], row)

    def test_table_claim_lands_on_page_three(self):
        case = self._case_for(
            "Hyperparameters used in training",
            case_id="table-caption",
            claim_text=TABLE_CAPTION,
            answer=f"{TABLE_CAPTION} [E1]",
            expected_page=3,
            expected_pages=(3,),
            expected_quote_substring="Hyperparameters used in training",
            content_type="table",
        )
        report = run_evaluation([case], corpus=self.corpus)
        row = report.cases[0]
        self.assertFalse(row.get("skipped"), row)
        self.assertFalse(row["wrong_page"], row)
        self.assertFalse(row["false_precise"], row)
        self.assertIn(3, row["pages"], row)
        self.assertTrue(row["localized"] or row["page_only_success"], row)

    def test_retrieval_mode_uses_recall_pool_without_live_index(self):
        case = self._case_for(
            "thirty days written notice",
            case_id="retrieve-notice",
            claim_text=NOTICE,
            answer=f"{NOTICE} [E1]",
            expected_page=1,
            expected_pages=(1,),
            expected_quote_substring="thirty days written notice",
            question="How much notice is required to end employment?",
        )
        chunk = find_chunk_containing(self.corpus.chunks, "thirty days written notice")
        assert chunk is not None

        def retrieve_fn(question, document_ids=None, generate=False):
            del question, document_ids, generate
            source = {
                "evidence_id": "E2",
                "chunk_id": chunk["chunk_id"],
                "document_id": self.document_id,
                "filename": "eval-corpus.pdf",
                "page": 1,
                "relevance": 88,
                "snippet": NOTICE,
                "text": chunk["text"],
                "citation_eligible": True,
            }
            return {"sources": [source], "recall_candidates": [source]}

        report = run_evaluation(
            [case],
            mode="retrieval",
            corpus=self.corpus,
            retrieve_fn=retrieve_fn,
        )
        row = report.cases[0]
        self.assertFalse(row.get("skipped"), row)
        self.assertTrue(row["retrieval_hit"], row)
        self.assertTrue(row["marker_present"], row)
        self.assertIn(1, row["pages"], row)


class TestCliEmptyCases(unittest.TestCase):
    def test_empty_cases_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out.json")
            cases_path = os.path.join(tmp, "empty_cases.json")
            Path(cases_path).write_text(
                json.dumps({"description": "empty", "cases": []}),
                encoding="utf-8",
            )
            code = main(["--cases", cases_path, "--out", out])
            self.assertEqual(code, 0)
            payload = json.loads(Path(out).read_text(encoding="utf-8"))
        self.assertEqual(payload["case_count"], 0)
        self.assertEqual(payload["evaluated"], 0)


class TestPrepareEvalDocument(unittest.TestCase):
    def test_chunks_cover_all_three_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "prep.db")
            pdf_path = os.path.join(tmp, "prep.pdf")
            _write_eval_pdf(pdf_path, [_native_page(), _figure_page(), _table_page()])
            with patch("database.db.SQLITE_DB_PATH", db_path):
                init_db()
                document_id = create_document("prep.pdf")
                corpus = prepare_eval_document(pdf_path, document_id=document_id)
                self.assertIsInstance(corpus, EvalCorpus)
                self.assertGreaterEqual(len(corpus.chunks), 1)
                joined = " ".join(str(chunk.get("text") or "") for chunk in corpus.chunks)
                self.assertIn("thirty days written notice", joined)
                self.assertIn("Pipeline overview", joined)
                self.assertIn("Hyperparameters used in training", joined)
                delete_document(document_id)


if __name__ == "__main__":
    unittest.main()
