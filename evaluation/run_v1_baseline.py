"""
RAG V1 Baseline Benchmark Runner

Uses the CURRENT V1 pipeline unchanged:
  - rag.retrieve_chunks
  - rag.ask_question

Does NOT modify retrieval, chunking, embeddings, prompts, or APIs.

Usage (from repo root):
  python -m evaluation.run_v1_baseline
  python -m evaluation.run_v1_baseline --skip-generation
  python -m evaluation.run_v1_baseline --limit 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from config import SIMILARITY_THRESHOLD, TOP_K
from rag import ask_question, retrieve_chunks

from evaluation.v1_benchmark_dataset import V1_BENCHMARK, dataset_stats


RESULTS_DIR = Path(__file__).resolve().parent / "results"
REFUSAL_PATTERNS = [
    r"don't have enough information",
    r"do not have enough information",
    r"no relevant information",
    r"not in the (provided )?context",
    r"insufficient (information|evidence)",
    r"cannot (find|determine|answer)",
    r"i'm unable to",
    r"i am unable to",
]


def _quiet_call(fn, *args, **kwargs):
    """Call V1 functions while suppressing their debug prints."""
    buf = StringIO()
    with redirect_stdout(buf):
        return fn(*args, **kwargs)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def keyword_hit(text: str, keywords: list[str]) -> tuple[bool, list[str]]:
    if not keywords:
        return False, []
    norm = _normalize(text)
    found = [kw for kw in keywords if _normalize(kw) in norm]
    # Hit if ANY keyword found (lenient automated retrieval hit)
    # Also track fraction for reporting
    return len(found) > 0, found


def all_keywords_hit(text: str, keywords: list[str]) -> tuple[bool, list[str]]:
    if not keywords:
        return False, []
    norm = _normalize(text)
    found = [kw for kw in keywords if _normalize(kw) in norm]
    return len(found) == len(keywords), found


def looks_like_refusal(answer: str) -> bool:
    norm = _normalize(answer)
    return any(re.search(p, norm) for p in REFUSAL_PATTERNS)


def evaluate_retrieval(item: dict[str, Any]) -> dict[str, Any]:
    question = item["question"]
    # Conversational rewrite happens inside ask_question only.
    # For pure retrieval baseline on follow-ups, retrieve the raw question
    # (honest V1 behavior when rewrite is skipped) AND also the rewritten
    # path is measured in the generation stage.
    t0 = time.perf_counter()
    result = _quiet_call(retrieve_chunks, question, None)
    latency_ms = (time.perf_counter() - t0) * 1000

    chunks = result.get("chunks") or []
    distances = result.get("distances") or []
    metadata = result.get("metadata") or []
    ids = result.get("ids") or []

    joined = "\n".join(chunks)
    keywords = item.get("expected_keywords") or []
    expected_pages = set(item.get("expected_pages") or [])
    expected_doc = item.get("expected_document")

    any_kw, found_kw = keyword_hit(joined, keywords)
    all_kw, found_all = all_keywords_hit(joined, keywords)

    retrieved_pages = [
        m.get("page_number") for m in metadata if m and m.get("page_number") is not None
    ]
    retrieved_docs = [m.get("filename") for m in metadata if m]

    page_hits = [p for p in retrieved_pages if p in expected_pages]
    page_hit = len(page_hits) > 0 if expected_pages else False
    page_recall = (
        len(set(page_hits)) / len(expected_pages) if expected_pages else None
    )

    doc_hit = (
        expected_doc in retrieved_docs if expected_doc else False
    )

    # Rank of first keyword / page hit for MRR
    rank_kw = None
    for i, chunk in enumerate(chunks, start=1):
        hit, _ = keyword_hit(chunk, keywords)
        if hit:
            rank_kw = i
            break

    rank_page = None
    if expected_pages:
        for i, page in enumerate(retrieved_pages, start=1):
            if page in expected_pages:
                rank_page = i
                break

    # Prefer page rank for MRR when pages are labeled; else keyword rank
    mrr_rank = rank_page if rank_page is not None else rank_kw
    # For answerable items, a "hit" is page hit OR keyword hit
    if item.get("answerable", True):
        hit_at_k = bool(page_hit or any_kw)
    else:
        # For unanswerable, retrieval "success" is not required;
        # we still record whether stray docs were retrieved.
        hit_at_k = False

    filtered = [
        (c, d, m, i)
        for c, d, m, i in zip(chunks, distances, metadata, ids)
        if d <= SIMILARITY_THRESHOLD
    ]

    return {
        "latency_ms": round(latency_ms, 1),
        "n_retrieved": len(chunks),
        "n_after_threshold": len(filtered),
        "distances": [round(float(d), 4) for d in distances],
        "retrieved_pages": retrieved_pages,
        "retrieved_docs": retrieved_docs,
        "chunk_ids": ids,
        "keyword_any_hit": any_kw,
        "keyword_all_hit": all_kw,
        "keywords_found": found_kw if any_kw else found_all,
        "page_hit": page_hit,
        "page_recall_at_k": page_recall,
        "doc_hit": doc_hit,
        "hit_at_k": hit_at_k,
        "mrr_rank": mrr_rank,
        "mrr": (1.0 / mrr_rank) if mrr_rank else 0.0,
        "top_chunk_preview": (chunks[0][:220] if chunks else ""),
    }


def evaluate_generation(item: dict[str, Any]) -> dict[str, Any]:
    question = item["question"]
    history = item.get("history")

    t0 = time.perf_counter()
    response = _quiet_call(ask_question, question, history, None)
    latency_ms = (time.perf_counter() - t0) * 1000

    if isinstance(response, dict):
        answer = response.get("answer") or ""
        sources = response.get("sources") or []
    else:
        # Defensive: older callers sometimes treated response as string
        answer = str(response)
        sources = []

    keywords = item.get("expected_keywords") or []
    expected_pages = set(item.get("expected_pages") or [])
    expected_doc = item.get("expected_document")
    answerable = item.get("answerable", True)

    any_kw, found_kw = keyword_hit(answer, keywords)
    all_kw, _ = all_keywords_hit(answer, keywords)

    source_pages = [s.get("page") for s in sources if isinstance(s, dict)]
    source_docs = [s.get("filename") for s in sources if isinstance(s, dict)]
    source_page_hit = (
        any(p in expected_pages for p in source_pages) if expected_pages else False
    )
    source_doc_hit = expected_doc in source_docs if expected_doc else False

    refused = looks_like_refusal(answer)
    empty_sources = len(sources) == 0

    if answerable:
        # Automated answer correctness proxy: any expected keyword in answer
        answer_correct_auto = any_kw if keywords else None
        citation_correct_auto = source_page_hit if expected_pages else source_doc_hit
        unanswerable_correct = None
    else:
        answer_correct_auto = None
        citation_correct_auto = None
        # Correct refusal: refusal language OR empty sources after filter
        unanswerable_correct = bool(refused or empty_sources)

    return {
        "latency_ms": round(latency_ms, 1),
        "answer": answer,
        "answer_preview": answer[:400],
        "n_sources": len(sources),
        "source_pages": source_pages,
        "source_docs": source_docs,
        "sources": sources,
        "keyword_any_hit": any_kw,
        "keyword_all_hit": all_kw,
        "keywords_found": found_kw,
        "source_page_hit": source_page_hit,
        "source_doc_hit": source_doc_hit,
        "refused": refused,
        "empty_sources": empty_sources,
        "answer_correct_auto": answer_correct_auto,
        "citation_correct_auto": citation_correct_auto,
        "unanswerable_correct_auto": unanswerable_correct,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [r for r in rows if r["item"]["answerable"]]
    unanswerable = [r for r in rows if not r["item"]["answerable"]]

    def avg(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    def rate(flags):
        flags = [f for f in flags if f is not None]
        return round(sum(1 for f in flags if f) / len(flags), 4) if flags else None

    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["item"]["category"]].append(r)

    retrieval = {
        "hit_at_k": rate([r["retrieval"]["hit_at_k"] for r in answerable]),
        "page_hit_at_k": rate([r["retrieval"]["page_hit"] for r in answerable if r["item"].get("expected_pages")]),
        "doc_hit_at_k": rate([r["retrieval"]["doc_hit"] for r in answerable if r["item"].get("expected_document")]),
        "mrr": avg([r["retrieval"]["mrr"] for r in answerable]),
        "avg_page_recall_at_k": avg(
            [
                r["retrieval"]["page_recall_at_k"]
                for r in answerable
                if r["retrieval"]["page_recall_at_k"] is not None
            ]
        ),
        "avg_latency_ms": avg([r["retrieval"]["latency_ms"] for r in rows]),
        "avg_n_after_threshold": avg(
            [r["retrieval"]["n_after_threshold"] for r in rows]
        ),
    }

    generation = None
    if any(r.get("generation") for r in rows):
        gens_a = [r["generation"] for r in answerable if r.get("generation")]
        gens_u = [r["generation"] for r in unanswerable if r.get("generation")]
        generation = {
            "answer_keyword_hit_rate": rate(
                [g["answer_correct_auto"] for g in gens_a]
            ),
            "citation_page_hit_rate": rate(
                [g["citation_correct_auto"] for g in gens_a]
            ),
            "unanswerable_correct_rate": rate(
                [g["unanswerable_correct_auto"] for g in gens_u]
            ),
            "refusal_rate_on_unanswerable": rate([g["refused"] for g in gens_u]),
            "avg_latency_ms": avg(
                [r["generation"]["latency_ms"] for r in rows if r.get("generation")]
            ),
        }

    per_category = {}
    for cat, items in sorted(by_cat.items()):
        ans = [r for r in items if r["item"]["answerable"]]
        per_category[cat] = {
            "n": len(items),
            "retrieval_hit_at_k": rate([r["retrieval"]["hit_at_k"] for r in ans])
            if ans
            else None,
            "answer_keyword_hit_rate": rate(
                [
                    r["generation"]["answer_correct_auto"]
                    for r in ans
                    if r.get("generation")
                ]
            )
            if ans
            else None,
        }

    return {
        "dataset": dataset_stats(),
        "config": {
            "TOP_K": TOP_K,
            "SIMILARITY_THRESHOLD": SIMILARITY_THRESHOLD,
            "pipeline": "V1 unchanged (rag.retrieve_chunks / rag.ask_question)",
        },
        "retrieval": retrieval,
        "generation": generation,
        "per_category": per_category,
    }


def pick_representative_failures(rows: list[dict[str, Any]], limit: int = 10) -> list[dict]:
    failures = []
    for r in rows:
        item = r["item"]
        reasons = []
        if item["answerable"] and not r["retrieval"]["hit_at_k"]:
            reasons.append("retrieval_miss")
        gen = r.get("generation")
        if gen:
            if item["answerable"] and gen["answer_correct_auto"] is False:
                reasons.append("answer_keyword_miss")
            if item["answerable"] and gen["citation_correct_auto"] is False:
                reasons.append("citation_page_miss")
            if (not item["answerable"]) and gen["unanswerable_correct_auto"] is False:
                reasons.append("failed_to_refuse")
        if reasons:
            failures.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "question": item["question"],
                    "reasons": reasons,
                    "expected_pages": item.get("expected_pages"),
                    "retrieved_pages": r["retrieval"]["retrieved_pages"],
                    "answer_preview": (gen or {}).get("answer_preview", ""),
                    "source_pages": (gen or {}).get("source_pages", []),
                }
            )
    # Prefer diverse categories
    failures.sort(key=lambda f: (len(f["reasons"]), f["category"], f["id"]))
    return failures[:limit]


def write_report(summary: dict, failures: list, path: Path) -> None:
    ret = summary["retrieval"]
    gen = summary["generation"]
    ds = summary["dataset"]

    lines = [
        "# DocuSage RAG V1 Baseline Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This report measures the **current V1 RAG pipeline unchanged**.",
        "No hybrid retrieval, BM25, reranker, CRAG, chunking, or prompt changes were applied.",
        "",
        "## Dataset",
        "",
        f"- Size: **{ds['total']}** questions",
        f"- Answerable: {ds['answerable']}",
        f"- Unanswerable: {ds['unanswerable']}",
        f"- Categories: `{ds['by_category']}`",
        f"- Indexed docs used: `MACHINE LEARNING.pdf`, `football_rules.pdf`",
        "",
        "## Config (V1)",
        "",
        f"- TOP_K = `{summary['config']['TOP_K']}`",
        f"- SIMILARITY_THRESHOLD = `{summary['config']['SIMILARITY_THRESHOLD']}`",
        f"- Pipeline = `{summary['config']['pipeline']}`",
        "",
        "## Metric legend",
        "",
        "### Automated",
        "- **Retrieval Hit@K**: expected page appears in top-K metadata **or** any expected keyword appears in retrieved text",
        "- **Page Hit@K / Page Recall@K**: based on `page_number` metadata vs `expected_pages`",
        "- **MRR**: reciprocal rank of first page hit (else first keyword hit)",
        "- **Answer keyword hit**: any expected keyword appears in generated answer (proxy, not human judgment)",
        "- **Citation page hit**: any returned source page is in `expected_pages`",
        "- **Unanswerable correct**: refusal-like answer **or** empty sources",
        "",
        "### Manual (not scored here)",
        "- Nuanced answer correctness / completeness",
        "- Whether citations are the chunks the model actually used",
        "- Hallucinated details that still contain a keyword",
        "",
        "## Retrieval results (automated)",
        "",
        f"- Hit@K: **{(ret['hit_at_k'] or 0)*100:.1f}%**",
        f"- Page Hit@K: **{(ret['page_hit_at_k'] or 0)*100:.1f}%**",
        f"- Doc Hit@K: **{(ret['doc_hit_at_k'] or 0)*100:.1f}%**",
        f"- MRR: **{ret['mrr']}**",
        f"- Avg Page Recall@K: **{ret['avg_page_recall_at_k']}**",
        f"- Avg retrieval latency: **{ret['avg_latency_ms']} ms**",
        f"- Avg chunks after threshold: **{ret['avg_n_after_threshold']}**",
        "",
    ]

    if gen:
        lines += [
            "## Generation / citation results (automated)",
            "",
            f"- Answer keyword hit rate: **{(gen['answer_keyword_hit_rate'] or 0)*100:.1f}%**",
            f"- Citation page hit rate: **{(gen['citation_page_hit_rate'] or 0)*100:.1f}%**",
            f"- Unanswerable correct rate: **{(gen['unanswerable_correct_rate'] or 0)*100:.1f}%**",
            f"- Refusal language rate on unanswerable: **{(gen['refusal_rate_on_unanswerable'] or 0)*100:.1f}%**",
            f"- Avg end-to-end ask_question latency: **{gen['avg_latency_ms']} ms**",
            "",
        ]
    else:
        lines += [
            "## Generation / citation results",
            "",
            "_Skipped (`--skip-generation`)._",
            "",
        ]

    lines += ["## Per-category snapshot", ""]
    for cat, stats in summary["per_category"].items():
        lines.append(
            f"- **{cat}** (n={stats['n']}): retrieval_hit={stats['retrieval_hit_at_k']}, "
            f"answer_kw={stats['answer_keyword_hit_rate']}"
        )

    lines += [
        "",
        "## Common failure patterns",
        "",
        "1. **Follow-up / conversational questions** retrieve poorly on the raw short question unless rewrite succeeds.",
        "2. **Exact numbers/names** can miss when chunk boundaries or OCR/text extraction noise hide the token.",
        "3. **Comparison / multi-chunk** questions often retrieve only one side of the comparison.",
        "4. **Unanswerable** items may still retrieve loosely related football/ML chunks below/around threshold.",
        "5. **Citation page mismatch** when a related but wrong page is nearer in embedding space.",
        "",
        "## Representative failures",
        "",
    ]

    if not failures:
        lines.append("_No automated failures recorded._")
    else:
        for i, f in enumerate(failures, 1):
            lines += [
                f"### {i}. `{f['id']}` ({f['category']})",
                f"- Q: {f['question']}",
                f"- Reasons: {', '.join(f['reasons'])}",
                f"- Expected pages: {f['expected_pages']}",
                f"- Retrieved pages: {f['retrieved_pages']}",
                f"- Source pages: {f['source_pages']}",
                f"- Answer preview: {f['answer_preview'][:240]!r}",
                "",
            ]

    lines += [
        "## Reproducibility",
        "",
        "```bash",
        "python -m evaluation.run_v1_baseline",
        "```",
        "",
        "Dataset file: `evaluation/v1_benchmark_dataset.py`",
        "JSON results: `evaluation/results/v1_baseline_latest.json`",
        "",
        "Keep the dataset fixed when comparing V2 changes.",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run DocuSage RAG V1 baseline benchmark")
    parser.add_argument("--limit", type=int, default=None, help="Run only first N items")
    parser.add_argument(
        "--skip-generation",
        action="store_true",
        help="Only run retrieval metrics (faster; no LLM calls)",
    )
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Comma-separated question ids to run",
    )
    args = parser.parse_args(argv)

    items = list(V1_BENCHMARK)
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        items = [i for i in items if i["id"] in wanted]
    if args.limit:
        items = items[: args.limit]

    print("=" * 70)
    print("DOCUSAGE RAG V1 BASELINE BENCHMARK")
    print("=" * 70)
    print(f"Questions: {len(items)}")
    print(f"TOP_K={TOP_K}  SIMILARITY_THRESHOLD={SIMILARITY_THRESHOLD}")
    print(f"Generation: {'OFF' if args.skip_generation else 'ON'}")
    print()

    rows: list[dict[str, Any]] = []

    for idx, item in enumerate(items, start=1):
        print(f"[{idx}/{len(items)}] {item['id']} ({item['category']}) ...", flush=True)
        retrieval = evaluate_retrieval(item)
        generation = None if args.skip_generation else evaluate_generation(item)
        row = {"item": item, "retrieval": retrieval, "generation": generation}
        rows.append(row)

        flags = []
        flags.append("HIT" if retrieval["hit_at_k"] else "MISS")
        if generation:
            if item["answerable"]:
                flags.append(
                    "ANS_OK" if generation["answer_correct_auto"] else "ANS_MISS"
                )
                flags.append(
                    "CITE_OK" if generation["citation_correct_auto"] else "CITE_MISS"
                )
            else:
                flags.append(
                    "REFUSE_OK"
                    if generation["unanswerable_correct_auto"]
                    else "REFUSE_FAIL"
                )
        print("   " + " | ".join(flags))

    summary = aggregate(rows)
    failures = pick_representative_failures(rows)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "failures": failures,
        "rows": [
            {
                "id": r["item"]["id"],
                "category": r["item"]["category"],
                "answerable": r["item"]["answerable"],
                "question": r["item"]["question"],
                "retrieval": r["retrieval"],
                "generation": {
                    k: v
                    for k, v in (r["generation"] or {}).items()
                    if k not in {"sources"}  # keep JSON lighter; pages/docs kept
                }
                if r.get("generation")
                else None,
            }
            for r in rows
        ],
    }

    latest = RESULTS_DIR / "v1_baseline_latest.json"
    stamped = RESULTS_DIR / f"v1_baseline_{stamp}.json"
    latest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    stamped.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    report_path = Path(__file__).resolve().parent / "v1_baseline_report.md"
    write_report(summary, failures, report_path)

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(json.dumps(summary, indent=2))
    print()
    print(f"Wrote {latest}")
    print(f"Wrote {stamped}")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    # Ensure repo root is on sys.path when executed as a file.
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    raise SystemExit(main())
