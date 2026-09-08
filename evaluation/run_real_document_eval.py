"""
Real-document evaluation harness (item 12).

Measures claim → retrieval → localization → citation UI on adjudicated PDFs.
This is separate from the synthetic highlight benchmark. It does not change
retrieval, chunking, embeddings, BM25, RRF, or E-ID assignment.

Modes
  localization  canned/gold answer + one (or retrieved) source through
                finalize_answer_citations — tests mapping/UI
  retrieval     ask_question(generate=False) then the gold answer — tests
                whether the expected passage reached the recall pool

Case file: evaluation/real_document_cases.json
PDF root:   evaluation/real_pdfs/  (or absolute pdf_path per case)

Usage (from repo root):
  python -m evaluation.run_real_document_eval
  python -m evaluation.run_real_document_eval --mode retrieval
  python -m evaluation.run_real_document_eval --cases path.json --out path.json
"""

from __future__ import annotations

import argparse
import json
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from unittest.mock import MagicMock, patch

from claim_validator import finalize_answer_citations
from citation_resolver import _normalize_token
from chunking import build_chunks_from_pages
from database.db import init_db
from database.document_store import create_document
from database.evidence_store import list_chunk_evidence, replace_document_evidence
from document_paths import document_pdf_path
from evidence_mapping import build_document_evidence
from evidence_state import visible_sources
from pdf_extraction import extract_pages_from_pdf
from visual_evidence import VISUAL_TYPES

ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "real_document_cases.json"
PDF_DIR = ROOT / "real_pdfs"
RESULTS_DIR = ROOT / "results"

MODE_LOCALIZATION = "localization"
MODE_RETRIEVAL = "retrieval"
MODE_BOTH = "both"
VALID_MODES = {MODE_LOCALIZATION, MODE_RETRIEVAL, MODE_BOTH}

_MARKER_RE = re.compile(r"\[(E[1-9]\d*)(?:\:\s*\"[^\"]*\")?\]", re.IGNORECASE)


@dataclass
class RealDocumentCase:
    case_id: str
    document_id: str
    pdf_path: str = ""
    chunk_id: str = ""
    claim_text: str = ""
    answer: str = ""
    question: str = ""
    expected_page: int | None = None
    expected_pages: tuple[int, ...] = ()
    expected_quote_substring: str | None = None
    expected_chunk_id: str | None = None
    evidence_id: str = "E1"
    content_type: str | None = None
    mode: str | None = None
    notes: str | None = None


@dataclass
class EvalCorpus:
    """Indexed PDF + production chunks/evidence, without requiring Chroma."""

    document_id: str
    pdf_path: str
    chunks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RealDocumentReport:
    generated_at: str
    mode: str = MODE_LOCALIZATION
    case_count: int = 0
    skipped: int = 0
    evaluated: int = 0
    claim_verification_rate: float = 0.0
    evidence_localization_rate: float = 0.0
    highlight_precision_rate: float = 0.0
    wrong_page_rate: float = 0.0
    false_precise_rate: float = 0.0
    ui_dropout_rate: float = 0.0
    unsupported_claim_rate: float = 0.0
    retrieval_hit_rate: float | None = None
    page_only_success_rate: float | None = None
    cases: list[dict[str, Any]] = field(default_factory=list)


def _as_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def _expected_pages_from_raw(item: dict[str, Any]) -> tuple[int, ...]:
    pages: list[int] = []
    raw_pages = item.get("expected_pages")
    if isinstance(raw_pages, list):
        for value in raw_pages:
            number = _as_int(value)
            if number is not None and number >= 1:
                pages.append(number)
    expected_page = _as_int(item.get("expected_page"))
    if expected_page is not None and expected_page >= 1 and expected_page not in pages:
        pages.insert(0, expected_page)
    return tuple(pages)


def load_cases(path: Path = CASES_PATH) -> list[RealDocumentCase]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases: list[RealDocumentCase] = []
    for item in raw.get("cases") or []:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or "").strip()
        document_id = str(item.get("document_id") or "").strip()
        if not case_id or not document_id:
            continue
        evidence_id = _normalize_token(str(item.get("evidence_id") or "E1")) or "E1"
        expected_pages = _expected_pages_from_raw(item)
        cases.append(
            RealDocumentCase(
                case_id=case_id,
                document_id=document_id,
                pdf_path=str(item.get("pdf_path") or ""),
                chunk_id=str(item.get("chunk_id") or ""),
                claim_text=str(item.get("claim_text") or ""),
                answer=str(item.get("answer") or ""),
                question=str(item.get("question") or ""),
                expected_page=expected_pages[0] if expected_pages else _as_int(
                    item.get("expected_page")
                ),
                expected_pages=expected_pages,
                expected_quote_substring=(
                    str(item["expected_quote_substring"])
                    if item.get("expected_quote_substring")
                    else None
                ),
                expected_chunk_id=(
                    str(item["expected_chunk_id"])
                    if item.get("expected_chunk_id")
                    else None
                ),
                evidence_id=evidence_id,
                content_type=(
                    str(item["content_type"]) if item.get("content_type") else None
                ),
                mode=str(item["mode"]).strip() if item.get("mode") else None,
                notes=str(item["notes"]) if item.get("notes") else None,
            )
        )
    return cases


def _normalize_blob(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def find_chunk_containing(
    chunks: list[dict[str, Any]],
    needle: str,
) -> dict[str, Any] | None:
    text = _normalize_blob(needle)
    if not text:
        return None
    for chunk in chunks:
        blob = _normalize_blob(str(chunk.get("text") or chunk.get("snippet") or ""))
        if text in blob:
            return chunk
    return None


def prepare_eval_document(
    pdf_path: str | Path,
    *,
    document_id: str | None = None,
    filename: str | None = None,
) -> EvalCorpus:
    """
    Extract, chunk, and persist evidence for a PDF using production code.

    Does not embed or write Chroma. Tests/CI pass the returned chunks into
    evaluate_case so quote mapping can run offline.
    """
    path = Path(pdf_path)
    init_db()
    doc_id = document_id or create_document(filename or path.name)
    extraction = extract_pages_from_pdf(str(path))
    chunks = build_chunks_from_pages(extraction.pages, doc_id)
    for chunk in chunks:
        chunk.setdefault("document_id", doc_id)
    evidence = build_document_evidence(
        str(path),
        doc_id,
        extraction.pages,
        chunks,
        text_engine=extraction.engine_used,
    )
    replace_document_evidence(doc_id, evidence)
    return EvalCorpus(document_id=doc_id, pdf_path=str(path), chunks=chunks)


def _resolve_pdf(case: RealDocumentCase, corpus: EvalCorpus | None = None) -> Path | None:
    if corpus and corpus.pdf_path and Path(corpus.pdf_path).is_file():
        return Path(corpus.pdf_path)
    if case.pdf_path:
        candidate = Path(case.pdf_path)
        if candidate.is_file():
            return candidate
        alt = PDF_DIR / case.pdf_path
        if alt.is_file():
            return alt
    live = document_pdf_path(case.document_id)
    if live and Path(live).is_file():
        return Path(live)
    return None


def _chunk_map(corpus: EvalCorpus | None) -> dict[str, dict[str, Any]]:
    if corpus is None:
        return {}
    return {
        str(chunk.get("chunk_id")): chunk
        for chunk in corpus.chunks
        if chunk.get("chunk_id")
    }


def _resolve_chunk_id(
    case: RealDocumentCase,
    corpus: EvalCorpus | None = None,
) -> str:
    if case.chunk_id:
        return case.chunk_id
    if case.expected_chunk_id:
        return case.expected_chunk_id
    needle = case.expected_quote_substring or case.claim_text
    chunks = list(corpus.chunks) if corpus else []
    if not chunks:
        try:
            chunks = list_chunk_evidence(case.document_id)
        except Exception:
            chunks = []
    found = find_chunk_containing(chunks, needle or "")
    return str((found or {}).get("chunk_id") or "")


def _chunk_text(
    chunk_id: str,
    case: RealDocumentCase,
    corpus: EvalCorpus | None,
) -> str:
    mapped = _chunk_map(corpus)
    row = mapped.get(chunk_id) or {}
    text = str(row.get("text") or "")
    if text.strip():
        return text
    try:
        stored = next(
            (
                item
                for item in list_chunk_evidence(case.document_id)
                if str(item.get("chunk_id")) == chunk_id
            ),
            None,
        )
    except Exception:
        stored = None
    return str((stored or {}).get("snippet") or case.claim_text or "")


def _gold_answer(case: RealDocumentCase, evidence_id: str) -> str:
    answer = (case.answer or "").strip()
    if answer:
        if evidence_id != "E1":
            answer = re.sub(r"\[E1\b", f"[{evidence_id}", answer, flags=re.IGNORECASE)
        return answer
    claim = (case.claim_text or case.expected_quote_substring or "").strip()
    return f"{claim} [{evidence_id}]".strip()


def _marker_present(answer: str, evidence_id: str) -> bool:
    token = _normalize_token(evidence_id) or evidence_id
    for match in _MARKER_RE.finditer(answer or ""):
        found = _normalize_token(match.group(1) or "")
        if found == token:
            return True
    return False


def observed_pages(source: dict[str, Any] | None) -> set[int]:
    pages: set[int] = set()
    if not source:
        return pages
    for region in source.get("quote_regions") or []:
        if not isinstance(region, dict):
            continue
        page = _as_int(region.get("page"))
        if page is not None and page >= 1:
            pages.add(page)
    for key in ("page", "page_start", "page_end"):
        page = _as_int(source.get(key))
        if page is not None and page >= 1:
            pages.add(page)
    return pages


def _quote_blob(source: dict[str, Any] | None) -> str:
    if not source:
        return ""
    parts = [
        str(source.get("quote") or ""),
        str(source.get("snippet") or ""),
        str(source.get("claim_context") or ""),
    ]
    spans = source.get("source_spans") or []
    parts.extend(str(span) for span in spans)
    return " ".join(parts)


def _is_visual(content_type: str | None, expected: str | None) -> bool:
    kinds = {str(content_type or "").strip(), str(expected or "").strip()}
    return any(kind in VISUAL_TYPES for kind in kinds if kind)


def retrieval_hit(
    case: RealDocumentCase,
    retrieved: list[dict[str, Any]] | None,
) -> bool:
    rows = [row for row in (retrieved or []) if isinstance(row, dict)]
    if not rows:
        return False
    expected_chunk = case.expected_chunk_id or case.chunk_id
    if expected_chunk:
        if any(str(row.get("chunk_id") or "") == expected_chunk for row in rows):
            return True
    needle = _normalize_blob(case.expected_quote_substring or case.claim_text or "")
    if needle:
        for row in rows:
            blob = _normalize_blob(
                " ".join(
                    str(row.get(key) or "")
                    for key in ("text", "chunk_text", "snippet", "quote")
                )
            )
            if needle in blob:
                return True
    expected = set(case.expected_pages)
    if case.expected_page:
        expected.add(int(case.expected_page))
    if expected:
        for row in rows:
            if observed_pages(row) & expected:
                return True
    return False


def score_case_result(
    case: RealDocumentCase,
    *,
    finalized_answer: str,
    visible: list[dict[str, Any]],
    retrieved: list[dict[str, Any]] | None = None,
    evidence_id: str | None = None,
) -> dict[str, Any]:
    """Pure scoring: gold expectations vs finalized citation payload."""
    evidence_id = (
        _normalize_token(evidence_id or "")
        or _normalize_token(case.evidence_id)
        or "E1"
    )
    marker_present = _marker_present(finalized_answer, evidence_id)
    cited = None
    for source in visible:
        if _normalize_token(str(source.get("evidence_id") or "")) == evidence_id:
            cited = source
            break
    if cited is None and visible:
        cited = visible[0]

    in_final = cited is not None and any(
        _normalize_token(str(source.get("evidence_id") or "")) == evidence_id
        for source in visible
    )
    ui_dropout = marker_present and not in_final
    highlight = bool(cited and cited.get("quote_highlight_available"))
    pages = sorted(observed_pages(cited))
    expected = set(case.expected_pages)
    if case.expected_page:
        expected.add(int(case.expected_page))

    wrong_page = False
    if expected and cited is not None:
        observed = set(pages)
        wrong_page = expected.isdisjoint(observed)

    quote_ok = True
    if case.expected_quote_substring:
        quote_ok = _normalize_blob(case.expected_quote_substring) in _normalize_blob(
            _quote_blob(cited)
        )

    content_type = str(
        (cited or {}).get("content_type") or case.content_type or "native_text"
    )
    visual = _is_visual(content_type, case.content_type)
    false_precise = highlight and wrong_page
    page_ok = bool(expected) and cited is not None and not wrong_page
    if visual:
        localized = page_ok
        page_only_success = page_ok and not false_precise
    else:
        localized = highlight and not wrong_page and quote_ok
        page_only_success = False

    hit: bool | None = None
    if retrieved is not None:
        hit = retrieval_hit(case, retrieved)

    return {
        "case_id": case.case_id,
        "skipped": False,
        "marker_present": marker_present,
        "ui_dropout": ui_dropout,
        "highlight": highlight,
        "localized": localized,
        "wrong_page": wrong_page,
        "false_precise": false_precise,
        "quote_ok": quote_ok,
        "page_only_success": page_only_success,
        "unsupported_claim": not marker_present,
        "retrieval_hit": hit,
        "status": (cited or {}).get("quote_mapping_status"),
        "ui_status": (cited or {}).get("ui_status"),
        "confidence": (cited or {}).get("localization_confidence"),
        "pages": pages,
        "content_type": content_type,
        "selected_chunk_id": (cited or {}).get("chunk_id"),
        "evidence_id": evidence_id,
    }


@contextmanager
def _offline_chunk_lookups(pdf_path: str, chunks: list[dict[str, Any]]) -> Iterator[None]:
    """Serve chunk text/meta from memory so CI does not touch the live index."""
    by_id = {
        str(chunk.get("chunk_id")): chunk
        for chunk in chunks
        if chunk.get("chunk_id")
    }

    def record(chunk_id: str) -> tuple[str | None, dict[str, Any]]:
        row = by_id.get(str(chunk_id))
        if not row:
            return None, {}
        text = str(row.get("text") or "")
        page_start = _as_int(row.get("page_start") or row.get("page_number")) or 1
        page_end = _as_int(row.get("page_end")) or page_start
        meta = {
            "document_id": str(row.get("document_id") or ""),
            "filename": Path(pdf_path).name,
            "page_number": _as_int(row.get("page_number")) or page_start,
            "page_start": page_start,
            "page_end": page_end,
            "prev_chunk_id": str(row.get("prev_chunk_id") or ""),
            "next_chunk_id": str(row.get("next_chunk_id") or ""),
        }
        return text, meta

    def index_text(chunk_id: str) -> str:
        text, _meta = record(chunk_id)
        return text or ""

    def source_text(source: dict[str, Any]) -> str:
        return index_text(str((source or {}).get("chunk_id") or ""))

    def pdf_for(_document_id: str) -> str:
        return pdf_path

    def collection_get(ids=None, include=None, **_kwargs):
        del include
        kept: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for chunk_id in list(ids or []):
            text, meta = record(str(chunk_id))
            if not text:
                continue
            kept.append(str(chunk_id))
            documents.append(text)
            metadatas.append(meta)
        return {"ids": kept, "documents": documents, "metadatas": metadatas}

    collection = MagicMock()
    collection.get.side_effect = collection_get

    with (
        patch("quote_evidence._chunk_record_from_chroma", side_effect=record),
        patch(
            "quote_evidence._chunk_text_from_chroma",
            side_effect=lambda chunk_id: record(chunk_id)[0],
        ),
        patch("claim_orchestrator._chunk_text_from_index", side_effect=index_text),
        patch("claim_validator._chunk_text_for_source", side_effect=source_text),
        patch("claim_orchestrator.document_pdf_path", side_effect=pdf_for),
        patch("quote_evidence.document_pdf_path", side_effect=pdf_for),
        patch("claim_validator.document_pdf_path", side_effect=pdf_for),
        patch("rag.get_collection", return_value=collection),
    ):
        yield


def _build_source(
    case: RealDocumentCase,
    *,
    chunk_id: str,
    pdf_name: str,
    text: str,
    page: int | None,
    evidence_id: str,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "chunk_id": chunk_id,
        "document_id": case.document_id,
        "filename": pdf_name,
        "page": page,
        "relevance": 90,
        "snippet": (text or case.claim_text or "")[:180],
        "text": text,
        "citation_eligible": True,
        "evidence_state": "citeable",
    }


def _bind_retrieved_evidence(
    case: RealDocumentCase,
    sources: list[dict[str, Any]],
    recall: list[dict[str, Any]],
) -> tuple[str, str, list[dict[str, Any]]]:
    """Pick the retrieved E# whose chunk matches gold; keep E-IDs from retrieval."""
    pool = list(sources) + [
        row
        for row in recall
        if str(row.get("chunk_id") or "")
        not in {str(item.get("chunk_id") or "") for item in sources}
    ]
    match: dict[str, Any] | None = None
    expected_chunk = case.expected_chunk_id or case.chunk_id
    if expected_chunk:
        match = next(
            (row for row in sources if str(row.get("chunk_id") or "") == expected_chunk),
            None,
        )
        if match is None:
            recall_hit = next(
                (
                    row
                    for row in recall
                    if str(row.get("chunk_id") or "") == expected_chunk
                ),
                None,
            )
            if recall_hit is not None:
                match = next(
                    (
                        row
                        for row in sources
                        if str(row.get("chunk_id") or "")
                        == str(recall_hit.get("chunk_id") or "")
                    ),
                    recall_hit,
                )
    needle = (case.expected_quote_substring or case.claim_text or "").strip().lower()
    if match is None and needle:
        for row in pool:
            blob = " ".join(
                str(row.get(key) or "")
                for key in ("text", "chunk_text", "snippet")
            )
            if needle in blob.lower():
                chunk_id = str(row.get("chunk_id") or "")
                match = next(
                    (
                        item
                        for item in sources
                        if str(item.get("chunk_id") or "") == chunk_id
                    ),
                    row,
                )
                break
    evidence_id = (
        _normalize_token(str((match or {}).get("evidence_id") or ""))
        or _normalize_token(case.evidence_id)
        or "E1"
    )
    bound_sources = list(sources)
    if match is not None and not any(
        str(row.get("chunk_id") or "") == str(match.get("chunk_id") or "")
        for row in bound_sources
    ):
        item = dict(match)
        item["evidence_id"] = evidence_id
        bound_sources.append(item)
    return _gold_answer(case, evidence_id), evidence_id, bound_sources


def _retrieve(
    case: RealDocumentCase,
    retrieve_fn: Callable[..., dict[str, Any]] | None,
) -> dict[str, Any]:
    question = (case.question or case.claim_text or "").strip()
    if retrieve_fn is not None:
        return retrieve_fn(
            question,
            document_ids=[case.document_id],
            generate=False,
        )
    from rag import ask_question

    return ask_question(
        question,
        document_ids=[case.document_id],
        generate=False,
    )


def evaluate_case(
    case: RealDocumentCase,
    *,
    mode: str = MODE_LOCALIZATION,
    corpus: EvalCorpus | None = None,
    retrieve_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    requested = (case.mode or mode or MODE_LOCALIZATION).strip().lower()
    if requested not in VALID_MODES:
        requested = MODE_LOCALIZATION
    run_retrieval = requested in {MODE_RETRIEVAL, MODE_BOTH}

    pdf = _resolve_pdf(case, corpus)
    retrieved_rows: list[dict[str, Any]] | None = None
    sources: list[dict[str, Any]] = []
    recall: list[dict[str, Any]] = []
    evidence_id = _normalize_token(case.evidence_id) or "E1"
    answer = _gold_answer(case, evidence_id)

    if run_retrieval:
        question = (case.question or case.claim_text or "").strip()
        if not question:
            return {
                "case_id": case.case_id,
                "skipped": True,
                "reason": "no_question",
            }
        try:
            payload = _retrieve(case, retrieve_fn)
        except Exception as exc:
            return {
                "case_id": case.case_id,
                "skipped": True,
                "reason": f"retrieve_error:{exc.__class__.__name__}",
            }
        sources = list(payload.get("sources") or [])
        recall = list(payload.get("recall_candidates") or [])
        retrieved_rows = sources + recall
        answer, evidence_id, sources = _bind_retrieved_evidence(case, sources, recall)

    if not sources:
        if run_retrieval:
            result = score_case_result(
                case,
                finalized_answer=answer,
                visible=[],
                retrieved=retrieved_rows or [],
                evidence_id=evidence_id,
            )
            result["mode"] = requested
            result["retrieval_hit"] = False
            return result
        if pdf is None:
            return {
                "case_id": case.case_id,
                "skipped": True,
                "reason": "pdf_missing",
            }
        chunk_id = _resolve_chunk_id(case, corpus)
        if not chunk_id:
            return {
                "case_id": case.case_id,
                "skipped": True,
                "reason": "no_chunk",
            }
        text = _chunk_text(chunk_id, case, corpus)
        mapped = _chunk_map(corpus).get(chunk_id) or {}
        page = (
            case.expected_page
            or _as_int(mapped.get("page_number") or mapped.get("page_start"))
        )
        sources = [
            _build_source(
                case,
                chunk_id=chunk_id,
                pdf_name=pdf.name,
                text=text,
                page=page,
                evidence_id=evidence_id,
            )
        ]
        recall = list(sources)
        answer = _gold_answer(case, evidence_id)

    mapped_chunks = _chunk_map(corpus)
    if mapped_chunks:
        for row in list(sources) + list(recall):
            chunk_id = str(row.get("chunk_id") or "")
            if chunk_id and not str(row.get("text") or "").strip():
                text = str((mapped_chunks.get(chunk_id) or {}).get("text") or "")
                if text:
                    row["text"] = text

    def _finalize() -> dict[str, Any]:
        finalized_answer, enriched = finalize_answer_citations(
            answer,
            sources,
            resolve_regions=True,
            recall_candidates=recall or None,
        )
        visible = visible_sources(
            enriched,
            finalized_answer,
            recall_candidates=recall or None,
        )
        result = score_case_result(
            case,
            finalized_answer=finalized_answer,
            visible=visible,
            retrieved=retrieved_rows,
            evidence_id=evidence_id,
        )
        result["mode"] = requested
        result["final_answer"] = finalized_answer
        return result

    if corpus is not None:
        with _offline_chunk_lookups(corpus.pdf_path, corpus.chunks):
            return _finalize()
    return _finalize()


def run_evaluation(
    cases: list[RealDocumentCase] | None = None,
    *,
    mode: str = MODE_LOCALIZATION,
    corpus: EvalCorpus | None = None,
    retrieve_fn: Callable[..., dict[str, Any]] | None = None,
    limit: int | None = None,
) -> RealDocumentReport:
    selected = list(cases if cases is not None else load_cases())
    if limit is not None:
        selected = selected[: max(0, limit)]
    report = RealDocumentReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        case_count=len(selected),
    )
    if not selected:
        return report

    localized = 0
    highlights = 0
    wrong_pages = 0
    false_precise = 0
    dropouts = 0
    unsupported = 0
    page_only = 0
    visual_n = 0
    retrieval_hits = 0
    retrieval_n = 0

    for case in selected:
        result = evaluate_case(
            case,
            mode=mode,
            corpus=corpus,
            retrieve_fn=retrieve_fn,
        )
        report.cases.append(result)
        if result.get("skipped"):
            report.skipped += 1
            continue
        report.evaluated += 1
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
        if result.get("unsupported_claim"):
            unsupported += 1
        if _is_visual(result.get("content_type"), case.content_type):
            visual_n += 1
            if result.get("page_only_success"):
                page_only += 1
        if result.get("retrieval_hit") is not None:
            retrieval_n += 1
            if result.get("retrieval_hit"):
                retrieval_hits += 1

    evaluated = report.evaluated
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
    if visual_n:
        report.page_only_success_rate = page_only / visual_n
    if retrieval_n:
        report.retrieval_hit_rate = retrieval_hits / retrieval_n
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate real PDF claim-evidence localization"
    )
    parser.add_argument("--cases", default=str(CASES_PATH))
    parser.add_argument("--out", default=str(RESULTS_DIR / "real_document_latest.json"))
    parser.add_argument(
        "--mode",
        choices=sorted(VALID_MODES),
        default=MODE_LOCALIZATION,
        help="localization (default), retrieval, or both",
    )
    parser.add_argument(
        "--retrieve",
        action="store_true",
        help="Alias for --mode retrieval",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    mode = MODE_RETRIEVAL if args.retrieve else args.mode
    cases = load_cases(Path(args.cases))
    from evaluation.held_out_handbook import HELD_OUT_DOCUMENT_ID

    if cases and any(case.document_id == HELD_OUT_DOCUMENT_ID for case in cases):
        from evaluation.held_out_runtime import run_held_out_evaluation

        payload = run_held_out_evaluation(
            cases, index=True, mode=mode, limit=args.limit
        )
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(
            f"Cases: {payload.get('case_count')} "
            f"(skipped {payload.get('skipped')}, evaluated {payload.get('evaluated')})"
        )
        print(f"Mode: {mode}")
        print(f"Localization rate: {float(payload.get('evidence_localization_rate') or 0):.1%}")
        print(f"Wrong-page rate: {float(payload.get('wrong_page_rate') or 0):.1%}")
        print(f"False-precise rate: {float(payload.get('false_precise_rate') or 0):.1%}")
        print(f"UI dropout rate: {float(payload.get('ui_dropout_rate') or 0):.1%}")
        print(
            f"Unsupported claim rate: {float(payload.get('unsupported_claim_rate') or 0):.1%}"
        )
        if payload.get("retrieval_hit_rate") is not None:
            print(f"Retrieval hit rate: {float(payload['retrieval_hit_rate']):.1%}")
        print(f"Written: {out_path}")
        return 0
    report = run_evaluation(cases, mode=mode, limit=args.limit)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out)
    out_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")

    if report.case_count == 0:
        print(
            "No real-document cases found. Add adjudicated cases to "
            f"{CASES_PATH} and PDFs under {PDF_DIR}."
        )
        return 0

    print(f"Cases: {report.case_count} (skipped {report.skipped}, evaluated {report.evaluated})")
    print(f"Mode: {report.mode}")
    print(f"Localization rate: {report.evidence_localization_rate:.1%}")
    print(f"Wrong-page rate: {report.wrong_page_rate:.1%}")
    print(f"False-precise rate: {report.false_precise_rate:.1%}")
    print(f"UI dropout rate: {report.ui_dropout_rate:.1%}")
    print(f"Unsupported claim rate: {report.unsupported_claim_rate:.1%}")
    if report.retrieval_hit_rate is not None:
        print(f"Retrieval hit rate: {report.retrieval_hit_rate:.1%}")
    if report.page_only_success_rate is not None:
        print(f"Visual page-only success: {report.page_only_success_rate:.1%}")
    print(f"Written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
