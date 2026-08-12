# RAG V1 Baseline Evaluation

## Purpose

Establish a **measurable V1 baseline** before RAG V2 changes.

This evaluation uses the **current V1 pipeline unchanged**:
- `rag.retrieve_chunks`
- `rag.ask_question`

It does **not** add hybrid retrieval, BM25, rerankers, CRAG, agents, or chunking changes.

## Files

| File | Role |
|------|------|
| `v1_benchmark_dataset.py` | Fixed 40-question dataset |
| `run_v1_baseline.py` | Reproducible benchmark runner |
| `results/v1_baseline_latest.json` | Latest machine-readable results |
| `v1_baseline_report.md` | Human-readable baseline report |

Legacy scripts (`evaluation.py`, `generation_evaluation.py`, `evaluation_data.py`) are left untouched.

## Commands

From the repository root (`c:\document_assistant`), using the project virtualenv:

```bash
# Full baseline (retrieval + generation + citations)
.\.venv\Scripts\python.exe -m evaluation.run_v1_baseline

# Retrieval-only (no LLM calls)
.\.venv\Scripts\python.exe -m evaluation.run_v1_baseline --skip-generation

# Smoke test
.\.venv\Scripts\python.exe -m evaluation.run_v1_baseline --limit 3
```

On Unix-like shells:

```bash
.venv/bin/python -m evaluation.run_v1_baseline
```

## Dataset coverage

Questions are grounded in currently indexed Chroma documents:
- `MACHINE LEARNING.pdf`
- `football_rules.pdf`

Includes factual, semantic, exact-term, multi-chunk, comparison, conversational, and unanswerable items.

## Comparing V2 later

1. Keep `v1_benchmark_dataset.py` unchanged.
2. Re-run `python -m evaluation.run_v1_baseline`.
3. Diff `results/v1_baseline_latest.json` / `v1_baseline_report.md` against the V1 snapshot.
