"""
Real-document evaluation harness for claim-evidence localization.

Uses adjudicated cases tied to actual PDFs on disk (not synthetic fixtures).
Metrics are reported separately from the synthetic highlight benchmark.

Case file: evaluation/real_document_cases.json
PDF root:   evaluation/real_pdfs/  (or paths in each case)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claim_validator import finalize_answer_citations
from evidence_state import visible_sources

ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "real_document_cases.json"
PDF_DIR = ROOT / "real_pdfs"
RESULTS_DIR = ROOT / "results"


@dataclass
class RealDocumentCase:
    case_id: str
    document_id: str
    pdf_path: str
    chunk_id: str
    claim_text: str
    answer: str
    expected_page: int | None = None
    expected_quote_substring: str | None = None
    content_type: str | None = None
    notes: str | None = None


@dataclass
class RealDocumentReport:
    generated_at: str
    case_count: int = 0
    skipped: int = 0
    claim_verification_rate: float = 0.0
    evidence_localization_rate: float = 0.0
    highlight_precision_rate: float = 0.0
    wrong_page_rate: float = 0.0
    false_precise_rate: float = 0.0
    ui_dropout_rate: float = 0.0
    unsupported_claim_rate: float = 0.0
    cases: list[dict[str, Any]] = field(default_factory=list)


def load_cases(path: Path = CASES_PATH) -> list[RealDocumentCase]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases: list[RealDocumentCase] = []
    for item in raw.get("cases") or []:
        if not isinstance(item, dict):
            continue
        cases.append(
            RealDocumentCase(
                case_id=str(item.get("case_id") or ""),
                document_id=str(item.get("document_id") or ""),
                pdf_path=str(item.get("pdf_path") or ""),
                chunk_id=str(item.get("chunk_id") or ""),
                claim_text=str(item.get("claim_text") or ""),
                answer=str(item.get("answer") or ""),
                expected_page=item.get("expected_page"),
                expected_quote_substring=item.get("expected_quote_substring"),
                content_type=item.get("content_type"),
                notes=item.get("notes"),
            )
        )
    return [c for c in cases if c.case_id and c.chunk_id]


def _resolve_pdf(case: RealDocumentCase) -> Path | None:
    candidate = Path(case.pdf_path)
    if candidate.is_file():
        return candidate
    alt = PDF_DIR / case.pdf_path
    if alt.is_file():
        return alt
    return None


def evaluate_case(case: RealDocumentCase) -> dict[str, Any]:
    pdf = _resolve_pdf(case)
    if pdf is None:
        return {
            "case_id": case.case_id,
            "skipped": True,
            "reason": "pdf_missing",
        }

    source = {
        "evidence_id": "E1",
        "chunk_id": case.chunk_id,
        "document_id": case.document_id,
        "filename": pdf.name,
        "page": case.expected_page,
        "relevance": 90,
        "snippet": case.claim_text,
    }
    answer = case.answer or f"{case.claim_text} [E1]"
    finalized_answer, enriched = finalize_answer_citations(
        answer,
        [source],
        resolve_regions=True,
    )
    final = visible_sources(enriched, finalized_answer)
    row = final[0] if final else enriched[0] if enriched else {}
    regions = row.get("quote_regions") or []
    pages = sorted(
        {int(r["page"]) for r in regions if isinstance(r, dict) and r.get("page") is not None}
    )
    highlight = bool(row.get("quote_highlight_available"))
    marker_present = "[E1]" in finalized_answer
    in_final = bool(final)
    page = row.get("page")

    wrong_page = False
    if case.expected_page and pages:
        wrong_page = case.expected_page not in pages
    elif case.expected_page and page:
        wrong_page = int(page) != int(case.expected_page)

    quote_ok = True
    if case.expected_quote_substring:
        spans = row.get("source_spans") or []
        quote = row.get("quote") or ""
        joined = " ".join([str(s) for s in spans] + [str(quote)])
        quote_ok = case.expected_quote_substring.lower() in joined.lower()

    localized = highlight and not wrong_page and quote_ok
    false_precise = highlight and wrong_page

    return {
        "case_id": case.case_id,
        "skipped": False,
        "marker_present": marker_present,
        "ui_dropout": marker_present and not in_final,
        "highlight": highlight,
        "localized": localized,
        "wrong_page": wrong_page,
        "false_precise": false_precise,
        "quote_ok": quote_ok,
        "status": row.get("quote_mapping_status"),
        "confidence": row.get("localization_confidence"),
        "pages": pages,
        "content_type": row.get("content_type"),
    }


def run_evaluation() -> RealDocumentReport:
    cases = load_cases()
    report = RealDocumentReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        case_count=len(cases),
    )
    if not cases:
        report.skipped = 0
        return report

    evaluated = 0
    localized = 0
    highlights = 0
    wrong_pages = 0
    false_precise = 0
    dropouts = 0
    unsupported = 0

    for case in cases:
        result = evaluate_case(case)
        report.cases.append(result)
        if result.get("skipped"):
            report.skipped += 1
            continue
        evaluated += 1
        if result.get("localized"):
            localized += 1
        if result.get("highlight"):
            highlights += 1
        if result.get("wrong_page"):
            wrong_pages += 1
        if result.get("false_precise"):
            false_precise += 1
        if result.get("ui_dropout"):
            dropouts += 1
        if not result.get("marker_present"):
            unsupported += 1

    if evaluated:
        report.claim_verification_rate = localized / evaluated
        report.evidence_localization_rate = localized / evaluated
        report.highlight_precision_rate = (
            (highlights - false_precise) / highlights if highlights else 1.0
        )
        report.wrong_page_rate = wrong_pages / evaluated
        report.false_precise_rate = false_precise / evaluated
        report.ui_dropout_rate = dropouts / evaluated
        report.unsupported_claim_rate = unsupported / evaluated

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate real PDF evidence localization")
    parser.add_argument("--out", default=str(RESULTS_DIR / "real_document_latest.json"))
    args = parser.parse_args(argv)

    report = run_evaluation()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out)
    out_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")

    if report.case_count == 0:
        print(
            "No real-document cases found. Add adjudicated cases to "
            f"{CASES_PATH} and PDFs under {PDF_DIR}."
        )
        return 0

    print(f"Cases: {report.case_count} (skipped {report.skipped})")
    print(f"Localization rate: {report.evidence_localization_rate:.1%}")
    print(f"Wrong-page rate: {report.wrong_page_rate:.1%}")
    print(f"False-precise rate: {report.false_precise_rate:.1%}")
    print(f"UI dropout rate: {report.ui_dropout_rate:.1%}")
    print(f"Written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
