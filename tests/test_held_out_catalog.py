"""Held-out handbook catalog for item 12/14 (offline mapping, no live index)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database.db import init_db
from database.document_store import create_document, delete_document
from evaluation.held_out_handbook import (
    FACTS,
    HELD_OUT_DOCUMENT_ID,
    catalog_case_dicts,
    write_held_out_pdf,
)
from evaluation.run_real_document_eval import (
    CASES_PATH,
    find_chunk_containing,
    load_cases,
    prepare_eval_document,
    run_evaluation,
)


class TestHeldOutCatalogFile(unittest.TestCase):
    def test_catalog_meets_release_volume(self):
        cases = load_cases(CASES_PATH)
        native_loc = [
            case
            for case in cases
            if case.mode == "localization" and case.content_type == "native_text"
        ]
        retrieval = [case for case in cases if case.mode in {"retrieval", "both"}]
        self.assertGreaterEqual(len(cases), 20)
        self.assertGreaterEqual(len(native_loc), 10)
        self.assertGreaterEqual(len(retrieval), 10)
        self.assertTrue(all(case.document_id == HELD_OUT_DOCUMENT_ID for case in cases))

    def test_json_matches_handbook_facts(self):
        expected = catalog_case_dicts()
        raw = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(raw.get("cases"), expected)
        self.assertEqual(len(FACTS), 10)


class TestHeldOutCatalogEval(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name
        self.db_path = os.path.join(self.tmp, "held_out.db")
        self._db_patch = patch("database.db.SQLITE_DB_PATH", self.db_path)
        self._db_patch.start()
        init_db()
        self.pdf_path = os.path.join(self.tmp, "held_out_handbook.pdf")
        write_held_out_pdf(self.pdf_path)
        self.document_id = create_document("held_out_handbook.pdf")
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

    def _cases(self):
        cases = []
        for item in catalog_case_dicts():
            item = dict(item)
            item["document_id"] = self.document_id
            item["pdf_path"] = self.pdf_path
            cases.append(item)
        path = Path(self.tmp) / "cases.json"
        path.write_text(json.dumps({"cases": cases}), encoding="utf-8")
        return load_cases(path)

    def _retrieve_fn(self, question, document_ids=None, generate=False):
        del document_ids, generate
        needle = ""
        for fact in FACTS:
            if fact["question"] == question or fact["quote"].lower() in question.lower():
                needle = str(fact["quote"])
                break
        if not needle:
            needle = question
        chunk = find_chunk_containing(self.corpus.chunks, needle)
        if chunk is None:
            return {"sources": [], "recall_candidates": []}
        source = {
            "evidence_id": "E1",
            "chunk_id": chunk["chunk_id"],
            "document_id": self.document_id,
            "filename": "held_out_handbook.pdf",
            "page": chunk.get("page_start") or chunk.get("page_number"),
            "relevance": 90,
            "snippet": str(chunk.get("text") or "")[:180],
            "text": chunk["text"],
            "citation_eligible": True,
        }
        return {"sources": [source], "recall_candidates": [source]}

    def test_ten_native_and_ten_retrieval_evaluate(self):
        report = run_evaluation(
            self._cases(),
            corpus=self.corpus,
            retrieve_fn=self._retrieve_fn,
        )
        self.assertEqual(report.skipped, 0, report.cases)
        self.assertEqual(report.evaluated, 20)
        failed = [
            row
            for row in report.cases
            if not row.get("localized")
            or row.get("wrong_page")
            or row.get("ui_dropout")
            or row.get("false_precise")
            or row.get("unsupported_claim")
            or (row.get("mode") == "retrieval" and not row.get("retrieval_hit"))
        ]
        self.assertEqual(failed, [])
        self.assertGreaterEqual(report.evidence_localization_rate, 0.95)
        self.assertEqual(report.ui_dropout_rate, 0.0)
        self.assertLessEqual(report.wrong_page_rate, 0.02)
        self.assertEqual(report.retrieval_hit_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
