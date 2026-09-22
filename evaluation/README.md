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

## Highlight + claim verification eval

Measures quote→PDF highlight success, claim marker validation, and quote-region cache hits.

| File | Role |
|------|------|
| `highlight_benchmark_dataset.py` | Fixed highlight + claim cases |
| `run_highlight_eval.py` | Offline harness (synthetic PDFs + SQLite evidence) |
| `results/highlight_latest.json` | Latest machine-readable results |

```bash
.\.venv\Scripts\python.exe -m evaluation.run_highlight_eval
.\.venv\Scripts\python.exe -m evaluation.run_highlight_eval --limit 2
```

Metrics reported:
- **Claim verification accuracy** — marker quote validation / repair
- **Evidence localization accuracy** — claim → source span → PDF region
- **Highlight precision** — highlighted span tightness vs full chunk
- **Fallback rate** — confident chunk/page only, no fake precision
- **Unresolved rate** — could not locate supporting text
- **Cache hit rate** — repeat quote/claim lookup from SQLite cache

## Real-document eval (item 12)

Held-out adjudicated PDFs, not the synthetic highlight fixture. Two modes:

- **localization** — gold answer with `[E#]` through `finalize_answer_citations` (mapping + citation UI)
- **retrieval** — `ask_question(..., generate=False)` then the gold answer (recall-pool hit + localization)

The default catalog is 20 cases (10 native-text localization + 10 retrieval) against a generated operations handbook (`evaluation/held_out_handbook.py` → `evaluation/real_pdfs/held_out_handbook.pdf`). Release eval indexes that PDF into an isolated store under `evaluation/results/held_out/` so the live app corpus is not written.

```bash
.\.venv\Scripts\python.exe -m evaluation.run_real_document_eval
.\.venv\Scripts\python.exe -m evaluation.run_real_document_eval --mode retrieval
.\.venv\Scripts\python.exe -m evaluation.run_real_document_eval --cases evaluation/real_document_cases.json --out evaluation/results/real_document_latest.json
```

Case file: `evaluation/real_document_cases.json`. Put additional PDFs in `evaluation/real_pdfs/` or set an absolute `pdf_path`. Metrics include localization, wrong-page, false-precise, UI dropout, unsupported claim, retrieval hit, and visual page-only success.

CI covers the harness with a generated multi-page native-text PDF (`test_real_document_eval.py`) plus the 20-case catalog (`test_held_out_catalog.py`). It does not change retrieval.

## Adversarial + regression gate (item 13)

Fail-closed pack: generic adversarial cases (Q×3 stability, paraphrases, wrong-doc scope, invented markers, visual false-precise, unrelated refusals) plus the item 1–12 regression modules.

```bash
.\.venv\Scripts\python.exe -m evaluation.run_adversarial_suite
.\.venv\Scripts\python.exe -m evaluation.run_adversarial_suite --skip-slow
.\.venv\Scripts\python.exe -m evaluation.run_adversarial_suite --frontend
```

Writes `evaluation/results/adversarial_latest.json`. Exit code 1 on any failure. Does not call a live LLM or change retrieval.

## Production acceptance / release certification (item 14)

Frozen launch bars. Item 12 measures; item 13 regresses; this command **certifies**.

| Gate | Bar |
|------|-----|
| Adversarial pack | 100% |
| Recall@pool (retrieval hit) | ≥ 92% |
| Post-rerank context recall | ≥ 90% |
| Grounding (supported claims) | ≥ 90% |
| Native-text localization | ≥ 95% |
| Wrong-page | ≤ 2% |
| False-precise highlight | ≤ 1% |
| Native-text UI dropout | 0% |
| Rerank zero-result when fused > 0 | 0% |
| Same-claim instability (Q×3) | ≤ 5% |
| Held-out evaluated cases (release) | ≥ 20 (≥ 10 native, ≥ 10 retrieval) |

```bash
.\.venv\Scripts\python.exe -m evaluation.run_acceptance_gates --profile ci
.\.venv\Scripts\python.exe -m evaluation.run_acceptance_gates --profile release
```

`--profile ci` is the engineering gate (adversarial pack + rerank invariant). `--profile release` is the ship stamp and **fails closed** if `evaluation/real_document_cases.json` is empty or rates are below bar. Vacuous 0% wrong-page on zero cases does not certify. Writes `evaluation/results/acceptance_latest.json`.

## Launch readiness audit (item 15)

Repeats the held-out suite (via the item 14 certificate), the 9 generic production-audit scenarios, load/latency, and failure injection. **Not a substitute for items 12/14.** Automated engineering can pass; `launch_approved` still requires `--signoff`.

```bash
.\.venv\Scripts\python.exe -m evaluation.run_launch_audit
.\.venv\Scripts\python.exe -m evaluation.run_launch_audit --run-release --signoff
```

Writes `evaluation/results/launch_audit_latest.json`. Exit code 1 if engineering probes fail. Without `--signoff`, engineering can pass while launch stays unapproved.


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
