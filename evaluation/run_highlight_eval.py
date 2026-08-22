"""
Highlight + claim verification + localization evaluation harness.

Metrics:
  - claim verification accuracy
  - evidence localization accuracy
  - highlight precision (span tightness vs chunk)
  - fallback rate
  - unresolved rate
  - cache hit rate

Usage (from repo root):
  python -m evaluation.run_highlight_eval
  python -m evaluation.run_highlight_eval --limit 3
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import unittest.mock as mock
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf as fitz

from claim_localizer import (
    STATUS_EXACT,
    STATUS_FALLBACK_CHUNK,
    STATUS_SEMANTIC_SPAN,
    STATUS_SENTENCE,
    STATUS_UNRESOLVED,
)
from citation_resolver import quotes_by_evidence_id
from claim_validator import finalize_answer_citations, validate_quote_against_chunk
from database.db import init_db
from database.document_store import create_document, delete_document
from database.evidence_store import get_quote_region_cache, replace_document_evidence
from chunking import build_chunks_from_pages
from evidence_mapping import SOURCE_NATIVE, build_document_evidence
from pdf_extraction import PRIMARY_ENGINE, extract_pages_from_pdf
from quote_evidence import resolve_claim_evidence, resolve_quote_evidence

from evaluation.highlight_benchmark_dataset import (
    CLAIM_VERIFICATION_BENCHMARK,
    HIGHLIGHT_BENCHMARK,
    LOCALIZATION_BENCHMARK,
    dataset_stats,
)


RESULTS_DIR = Path(__file__).resolve().parent / "results"

PRECISE_STATUSES = frozenset(
    {
        STATUS_EXACT,
        STATUS_SENTENCE,
        STATUS_SEMANTIC_SPAN,
        "exact",
        "normalized",
        "fuzzy_compact",
        "hyphen_fuzzy",
    }
)


def _write_text_pdf(path: str, page_texts: list[str]) -> None:
    """Write one sentence per line so extracted PDF plain text aligns with chunks."""
    doc = fitz.open()
    try:
        for text in page_texts:
            page = doc.new_page()
            y = 72.0
            for line in re.split(r"(?<=[.!?])\s+", text):
                line = line.strip()
                if not line:
                    continue
                page.insert_text((72, y), line)
                y += 16.0
        doc.save(path)
    finally:
        doc.close()


def _build_synthetic_evidence(
    document_id: str,
    chunk_id: str,
    chunk_text: str,
    *,
    page_number: int = 1,
) -> tuple[dict[str, Any], str, str]:
    """Return (evidence, actual_chunk_text, pdf_path) using production extraction."""
    tmp = tempfile.mkdtemp()
    pdf_path = os.path.join(tmp, "bench.pdf")
    _write_text_pdf(pdf_path, [chunk_text])
    extraction = extract_pages_from_pdf(pdf_path)
    pages = extraction.pages
    chunks = build_chunks_from_pages(pages, document_id)
    if chunks:
        chunk = dict(chunks[0])
        chunk["chunk_id"] = chunk_id
        actual_text = str(chunk.get("text") or chunk_text)
    else:
        chunk = {
            "chunk_id": chunk_id,
            "text": chunk_text,
            "page_start": page_number,
            "page_end": page_number,
            "page_number": page_number,
        }
        actual_text = chunk_text
    evidence = build_document_evidence(
        pdf_path,
        document_id,
        pages,
        [chunk],
        text_engine=extraction.engine_used,
    )
    return evidence, actual_text, pdf_path


def _region_area(regions: list[dict[str, Any]]) -> float:
    total = 0.0
    for region in regions or []:
        try:
            w = float(region["x1"]) - float(region["x0"])
            h = float(region["y1"]) - float(region["y0"])
            if w > 0 and h > 0:
                total += w * h
        except (KeyError, TypeError, ValueError):
            continue
    return total


def _prepare_case(
    document_id: str,
    chunk_id: str,
    chunk_text: str,
    *,
    page_number: int = 1,
) -> tuple[str, str]:
    evidence, actual_text, pdf_path = _build_synthetic_evidence(
        document_id,
        chunk_id,
        chunk_text,
        page_number=page_number,
    )
    replace_document_evidence(document_id, evidence)
    return actual_text, pdf_path


def _run_localization_case(
    case,
    *,
    document_id: str,
    chunk_id: str,
    pdf_path: str | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    with mock.patch("quote_evidence._chunk_text_from_chroma", return_value=case.chunk_text):
        first = resolve_claim_evidence(
            document_id=document_id,
            chunk_id=chunk_id,
            claim_text=case.claim_text,
            quote=case.quote,
            pdf_path=pdf_path,
        )
    first_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    with mock.patch("quote_evidence._chunk_text_from_chroma", return_value=case.chunk_text):
        second = resolve_claim_evidence(
            document_id=document_id,
            chunk_id=chunk_id,
            claim_text=case.claim_text,
            quote=case.quote,
            pdf_path=pdf_path,
        )
    second_ms = (time.perf_counter() - started) * 1000

    status = (first or {}).get("quote_mapping_status") or STATUS_UNRESOLVED
    highlight_ok = bool(first and first.get("quote_highlight_available"))
    regions = (first or {}).get("quote_regions") or []
    source_spans = (first or {}).get("source_spans") or []
    highlight_chars = sum(len(text) for text in source_spans)
    chunk_len = max(len(case.chunk_text), 1)
    highlight_ratio = highlight_chars / chunk_len if highlight_chars else 0.0

    passed = True
    if case.expect_precise_highlight and not highlight_ok:
        passed = False
    if not case.expect_precise_highlight and highlight_ok:
        passed = False
    if case.expect_unresolved and status not in {STATUS_UNRESOLVED, STATUS_FALLBACK_CHUNK, "not_in_chunk"}:
        passed = False
    if case.expect_fallback and status != STATUS_FALLBACK_CHUNK:
        passed = False
    if highlight_ok and status not in case.expect_statuses:
        passed = False
    if case.max_highlight_ratio is not None and highlight_ratio > case.max_highlight_ratio:
        passed = False

    return {
        "case_id": case.case_id,
        "passed": passed,
        "status": status,
        "highlight_ok": highlight_ok,
        "highlight_ratio": round(highlight_ratio, 3),
        "region_count": len(regions),
        "region_area": round(_region_area(regions), 2),
        "source_spans": source_spans,
        "cache_hit_second_call": second_ms < max(first_ms * 0.5, 10.0),
        "first_ms": round(first_ms, 2),
        "second_ms": round(second_ms, 2),
        "notes": case.notes,
    }


def _run_highlight_case(case, *, document_id: str, chunk_id: str, pdf_path: str | None) -> dict[str, Any]:
    with mock.patch("quote_evidence._chunk_text_from_chroma", return_value=case.chunk_text):
        first = resolve_quote_evidence(
            document_id=document_id,
            chunk_id=chunk_id,
            quote=case.quote,
            pdf_path=pdf_path,
        )
    highlight_ok = bool(first and first.get("quote_highlight_available"))
    status = (first or {}).get("quote_mapping_status") or "missing"
    in_chunk = validate_quote_against_chunk(case.quote, case.chunk_text)
    passed = (
        (not case.expect_in_chunk or in_chunk)
        and (case.expect_in_chunk or not in_chunk)
        and (not case.expect_highlight or highlight_ok)
        and (case.expect_highlight or not highlight_ok)
        and (not highlight_ok or status in case.expect_match_types)
    )
    return {
        "case_id": case.case_id,
        "passed": passed,
        "status": status,
        "highlight_ok": highlight_ok,
    }


def _run_claim_case(case, *, document_id: str, chunk_id: str, pdf_path: str | None) -> dict[str, Any]:
    source = {
        "evidence_id": case.evidence_id,
        "chunk_id": chunk_id,
        "document_id": document_id,
        "page": 1,
        "filename": "bench.pdf",
        "snippet": case.chunk_text[:120],
    }

    with mock.patch("claim_validator._chunk_text_for_source", return_value=case.chunk_text), mock.patch(
        "quote_evidence._chunk_text_from_chroma",
        return_value=case.chunk_text,
    ), mock.patch("claim_validator.document_pdf_path", return_value=pdf_path):
        answer, sources = finalize_answer_citations(
            case.answer,
            [source],
            resolve_regions=True,
        )

    item = sources[0] if sources else {}
    quote = item.get("quote")
    valid = bool(quote and validate_quote_against_chunk(quote, case.chunk_text))
    bare_marker = f"[{case.evidence_id}]" in answer and f'[{case.evidence_id}:"' not in case.answer
    marker_quotes = quotes_by_evidence_id(case.answer).get(case.evidence_id.upper(), [])
    if not marker_quotes:
        marker_quotes = quotes_by_evidence_id(case.answer).get(case.evidence_id, [])
    marker_valid = any(validate_quote_against_chunk(q, case.chunk_text) for q in marker_quotes)
    localized = bool(item.get("quote_highlight_available"))
    status = item.get("quote_mapping_status")
    source_spans = list(item.get("source_spans") or [])

    passed = True
    if case.expect_valid_quote and not marker_valid and not bare_marker:
        passed = False
    if not case.expect_valid_quote and marker_valid:
        passed = False
    if case.expect_precise_highlight and not localized and not source_spans:
        passed = False

    return {
        "case_id": case.case_id,
        "passed": passed,
        "quote_valid": valid,
        "marker_quote_valid": marker_valid,
        "localized": localized,
        "status": status,
        "source_spans": source_spans,
        "repaired_answer": answer,
    }


def _rate(rows: list[dict[str, Any]], key: str = "passed") -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row.get(key)) / len(rows)


def run_evaluation(*, limit: int | None = None) -> dict[str, Any]:
    init_db()
    loc_cases = LOCALIZATION_BENCHMARK[:limit] if limit else LOCALIZATION_BENCHMARK
    highlight_cases = HIGHLIGHT_BENCHMARK[:limit] if limit else HIGHLIGHT_BENCHMARK
    claim_cases = CLAIM_VERIFICATION_BENCHMARK[:limit] if limit else CLAIM_VERIFICATION_BENCHMARK

    document_id = create_document("highlight-eval.pdf")
    localization_results: list[dict[str, Any]] = []
    highlight_results: list[dict[str, Any]] = []

    try:
        for index, case in enumerate(loc_cases):
            chunk_id = f"{document_id}_loc_{index}"
            actual_text, pdf_path = _prepare_case(
                document_id, chunk_id, case.chunk_text, page_number=case.page_number
            )
            case = type(case)(**{**case.__dict__, "chunk_text": actual_text})
            localization_results.append(
                _run_localization_case(
                    case,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    pdf_path=pdf_path,
                )
            )

        for index, case in enumerate(highlight_cases):
            chunk_id = f"{document_id}_hl_{index}"
            actual_text, pdf_path = _prepare_case(
                document_id, chunk_id, case.chunk_text, page_number=case.page_number
            )
            case = type(case)(**{**case.__dict__, "chunk_text": actual_text})
            highlight_results.append(
                _run_highlight_case(
                    case,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    pdf_path=pdf_path,
                )
            )

        claim_results = []
        for index, case in enumerate(claim_cases):
            chunk_id = f"{document_id}_claim_{index}"
            actual_text, pdf_path = _prepare_case(document_id, chunk_id, case.chunk_text)
            case = type(case)(**{**case.__dict__, "chunk_text": actual_text})
            claim_results.append(
                _run_claim_case(
                    case,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    pdf_path=pdf_path,
                )
            )
    finally:
        delete_document(document_id)

    loc_pass = _rate(localization_results)
    claim_pass = _rate(claim_results)
    hl_pass = _rate(highlight_results)

    unresolved = sum(
        1
        for row in localization_results
        if row.get("status") in {STATUS_UNRESOLVED, "not_in_chunk"}
    )
    fallback = sum(1 for row in localization_results if row.get("status") == STATUS_FALLBACK_CHUNK)
    precise = sum(1 for row in localization_results if row.get("highlight_ok"))
    tight = sum(
        1
        for row in localization_results
        if row.get("highlight_ok") and (row.get("highlight_ratio") or 1) <= 0.55
    )
    cache_hits = sum(1 for row in localization_results if row.get("cache_hit_second_call"))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset_stats(),
        "summary": {
            "claim_verification_accuracy": round(claim_pass, 4),
            "evidence_localization_accuracy": round(loc_pass, 4),
            "highlight_precision": round(tight / precise if precise else 0.0, 4),
            "fallback_rate": round(fallback / len(localization_results) if localization_results else 0.0, 4),
            "unresolved_rate": round(unresolved / len(localization_results) if localization_results else 0.0, 4),
            "cache_hit_rate": round(cache_hits / len(localization_results) if localization_results else 0.0, 4),
            "legacy_highlight_pass_rate": round(hl_pass, 4),
            "localization_passed": sum(1 for row in localization_results if row.get("passed")),
            "localization_total": len(localization_results),
            "claim_passed": sum(1 for row in claim_results if row.get("passed")),
            "claim_total": len(claim_results),
        },
        "localization_results": localization_results,
        "highlight_results": highlight_results,
        "claim_results": claim_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run localization + claim verification eval")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--output",
        type=str,
        default=str(RESULTS_DIR / "highlight_latest.json"),
    )
    args = parser.parse_args(argv)

    report = run_evaluation(limit=args.limit)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["summary"]
    print("Localization eval complete")
    print(f"  Claim verification:          {summary['claim_verification_accuracy']:.1%}")
    print(f"  Evidence localization:       {summary['evidence_localization_accuracy']:.1%}")
    print(f"  Highlight precision (tight): {summary['highlight_precision']:.1%}")
    print(f"  Fallback rate:               {summary['fallback_rate']:.1%}")
    print(f"  Unresolved rate:             {summary['unresolved_rate']:.1%}")
    print(f"  Cache hit rate:              {summary['cache_hit_rate']:.1%}")
    print(f"  Wrote {output_path}")

    ok = (
        summary["claim_verification_accuracy"] >= 0.75
        and summary["evidence_localization_accuracy"] >= 0.75
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
