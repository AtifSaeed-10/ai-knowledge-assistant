# DocuSage RAG V1 Baseline Report

Generated: 2026-08-12T19:47:21.460347+00:00

This report measures the **current V1 RAG pipeline unchanged**.
No hybrid retrieval, BM25, reranker, CRAG, chunking, or prompt changes were applied.

## Dataset

- Size: **45** questions
- Answerable: 40
- Unanswerable: 5
- Categories: `{'factual': 13, 'semantic': 7, 'exact_term': 8, 'multi_chunk': 4, 'comparison': 5, 'conversational': 3, 'unanswerable': 5}`
- Indexed docs used: `MACHINE LEARNING.pdf`, `football_rules.pdf`

## Config (V1)

- TOP_K = `5`
- SIMILARITY_THRESHOLD = `0.7`
- Pipeline = `V1 unchanged (rag.retrieve_chunks / rag.ask_question)`

## Metric legend

### Automated
- **Retrieval Hit@K**: expected page appears in top-K metadata **or** any expected keyword appears in retrieved text
- **Page Hit@K / Page Recall@K**: based on `page_number` metadata vs `expected_pages`
- **MRR**: reciprocal rank of first page hit (else first keyword hit)
- **Answer keyword hit**: any expected keyword appears in generated answer (proxy, not human judgment)
- **Citation page hit**: any returned source page is in `expected_pages`
- **Unanswerable correct**: refusal-like answer **or** empty sources

### Manual (not scored here)
- Nuanced answer correctness / completeness
- Whether citations are the chunks the model actually used
- Hallucinated details that still contain a keyword

## Retrieval results (automated)

- Hit@K: **90.0%**
- Page Hit@K: **82.5%**
- Doc Hit@K: **100.0%**
- MRR: **0.785**
- Avg Page Recall@K: **0.8125**
- Avg retrieval latency: **27.4356 ms**
- Avg chunks after threshold: **4.4222**

## Generation / citation results (automated)

- Answer keyword hit rate: **97.5%**
- Citation page hit rate: **87.5%**
- Unanswerable correct rate: **100.0%**
- Refusal language rate on unanswerable: **100.0%**
- Avg end-to-end ask_question latency: **7851.5089 ms**

## Per-category snapshot

- **comparison** (n=5): retrieval_hit=0.8, answer_kw=1.0
- **conversational** (n=3): retrieval_hit=0.3333, answer_kw=1.0
- **exact_term** (n=8): retrieval_hit=1.0, answer_kw=1.0
- **factual** (n=13): retrieval_hit=0.9231, answer_kw=0.9231
- **multi_chunk** (n=4): retrieval_hit=1.0, answer_kw=1.0
- **semantic** (n=7): retrieval_hit=1.0, answer_kw=1.0
- **unanswerable** (n=5): retrieval_hit=None, answer_kw=None

## Common failure patterns

1. **Conversational follow-ups fail raw retrieval** (Hit@K only 33% for that category) — short pronouns like “it” miss the gold page unless query rewrite runs inside `ask_question`.
2. **Near-miss neighboring pages** — comparison/multi-chunk items often retrieve adjacent pages (e.g. 34–35 instead of 30; 23–24 instead of 22) so keywords may appear while page citations miss.
3. **Duplicate indexed copies** — the same PDF appears under multiple `document_id`s, so top-K often returns the same page repeated (e.g. five× page 77), wasting slots.
4. **Hard factual misses when the gold chunk isn’t nearest** — e.g. distance-metric list on page 11 loses to other “distance/geometric” pages.
5. **Citation page mismatch even when the answer looks right** — answer keyword hit can pass while cited pages are wrong/incomplete (seen on Unit II / learning-types questions).
6. **Unanswerable handling is strong in this run** (100% refusal) but retrieval still returns some in-domain chunks before threshold filtering — V2 should not regress this.

## Biggest V1 quality bottlenecks (from this baseline)

1. Pronoun / follow-up retrieval without rewrite at the retrieval-only layer  
2. No reranking of near-miss neighboring chunks/pages  
3. Duplicate documents in Chroma reducing effective diversity of top-K  
4. Page-level citation precision weaker than answer-keyword proxy (87.5% vs 97.5%)  
5. Multi-aspect questions under-covered by single dense top-5

## Representative failures

### 1. `cv_02` (conversational)
- Q: How does the referee signal it?
- Reasons: retrieval_miss
- Expected pages: [4]
- Retrieved pages: [77, 77, 77, 77, 63]
- Source pages: [4, 4, 4, 4, 45]
- Answer preview: 'The referee signals advantage by extending one or both arms forward at shoulder height.'

### 2. `cv_03` (conversational)
- Q: What are its main limitations?
- Reasons: retrieval_miss
- Expected pages: [36]
- Retrieved pages: [48, 48, 48, 107, 107]
- Source pages: [36, 36, 36, 70, 70]
- Answer preview: 'A decision tree that is very complex usually has a low bias. This makes it very difficult for the model to incorporate any new data. \n \nAlso, in the context, a small variance in the data can lead to a very high variance in the prediction, t'

### 3. `ml_f04` (factual)
- Q: What are the three main types of learning mentioned in the introduction?
- Reasons: citation_page_miss
- Expected pages: [2]
- Retrieved pages: [6, 6, 6, 17, 17]
- Source pages: [6, 6, 6, 17, 17]
- Answer preview: 'The three main types of learning mentioned in the introduction are:\n\n1. Supervised learning\n2. Unsupervised learning\n3. Reinforcement learning'

### 4. `fb_m01` (multi_chunk)
- Q: What disciplinary actions correspond to careless, reckless, and serious foul play?
- Reasons: citation_page_miss
- Expected pages: [22]
- Retrieved pages: [24, 24, 24, 24, 23]
- Source pages: [24, 24, 24, 24, 23]
- Answer preview: 'According to the context, the disciplinary actions correspond to:\n\n- Careless: A yellow card is shown for a stopping a promising attack (SPA) foul. A yellow card is more serious than the tactical nature of SPA.\n- Reckless: A yellow card is '

### 5. `ml_m01` (multi_chunk)
- Q: What topics are covered under Unit II on Supervised and Unsupervised Learning?
- Reasons: citation_page_miss
- Expected pages: [2, 4]
- Retrieved pages: [58, 58, 58, 61, 61]
- Source pages: [58, 58, 58, 61, 61]
- Answer preview: 'I don\'t have enough information in the provided context. The given snippet does not mention anything related to "Unit II on Supervised and Unsupervised Learning." The provided context appears to discuss Unsupervised Learning under the topic'

### 6. `ml_c02` (comparison)
- Q: How do classification trees differ from regression trees?
- Reasons: retrieval_miss, citation_page_miss
- Expected pages: [30]
- Retrieved pages: [34, 34, 34, 35, 35]
- Source pages: [34, 34, 34, 35, 35]
- Answer preview: 'Classification trees are used for classification-type problems, while regression trees are used for prediction-type problems. In other words, classification trees are used when the response variable is categorical (such as a consumer buying'

### 7. `ml_f06` (factual)
- Q: What are the four commonly used distance metrics in geometric models?
- Reasons: retrieval_miss, answer_keyword_miss, citation_page_miss
- Expected pages: [11]
- Retrieved pages: [89, 89, 89, 10, 10]
- Source pages: [89, 89, 89, 10, 10]
- Answer preview: "I don't have enough information in the provided context."

## Reproducibility

```bash
.\.venv\Scripts\python.exe -m evaluation.run_v1_baseline
```

Dataset file: `evaluation/v1_benchmark_dataset.py`
JSON results: `evaluation/results/v1_baseline_latest.json`

Keep the dataset fixed when comparing V2 changes.
