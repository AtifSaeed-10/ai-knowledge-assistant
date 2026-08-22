"""
Fixed benchmark cases for claim→evidence localization evaluation.

Each localization case specifies a claim (often paraphrased), source chunk,
optional verbatim quote, and expected localization behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from claim_localizer import (
    STATUS_EXACT,
    STATUS_FALLBACK_CHUNK,
    STATUS_SEMANTIC_SPAN,
    STATUS_SENTENCE,
    STATUS_UNRESOLVED,
)


@dataclass(frozen=True)
class LocalizationBenchmarkCase:
    case_id: str
    chunk_text: str
    claim_text: str
    quote: str | None = None
    expect_precise_highlight: bool = True
    expect_statuses: tuple[str, ...] = (
        STATUS_EXACT,
        STATUS_SENTENCE,
        STATUS_SEMANTIC_SPAN,
        "normalized",
        "fuzzy_compact",
        "exact",
    )
    expect_unresolved: bool = False
    expect_fallback: bool = False
    max_highlight_chars: int | None = None  # precision: highlighted span <= this fraction of chunk
    max_highlight_ratio: float | None = None
    page_number: int = 1
    notes: str = ""


@dataclass(frozen=True)
class HighlightBenchmarkCase:
    case_id: str
    chunk_text: str
    quote: str
    expect_in_chunk: bool = True
    expect_highlight: bool = True
    expect_match_types: tuple[str, ...] = ("exact", "normalized", "fuzzy_compact", "hyphen_fuzzy", STATUS_EXACT, STATUS_SENTENCE, STATUS_SEMANTIC_SPAN)
    page_number: int = 1
    notes: str = ""


@dataclass(frozen=True)
class ClaimVerificationCase:
    case_id: str
    answer: str
    chunk_text: str
    evidence_id: str = "E1"
    expect_valid_quote: bool = True
    expect_used: bool = True
    expect_localization: bool = False
    expect_precise_highlight: bool = False
    notes: str = ""


LOCALIZATION_BENCHMARK: list[LocalizationBenchmarkCase] = [
    LocalizationBenchmarkCase(
        case_id="claim_matches_one_sentence",
        chunk_text=(
            "Supervised learning uses labeled examples. "
            "Unsupervised learning finds patterns without labels."
        ),
        claim_text="Supervised learning uses labeled examples.",
        quote="labeled examples",
        expect_precise_highlight=True,
        expect_statuses=(STATUS_EXACT, STATUS_SENTENCE, STATUS_SEMANTIC_SPAN, "normalized", "fuzzy_compact"),
        max_highlight_ratio=0.55,
    ),
    LocalizationBenchmarkCase(
        case_id="claim_paraphrases_one_sentence",
        chunk_text=(
            "Supervised learning uses labeled examples. "
            "Unsupervised learning finds patterns without labels."
        ),
        claim_text="Supervised learning relies on labeled training data.",
        expect_precise_highlight=True,
        expect_statuses=(STATUS_SENTENCE, STATUS_SEMANTIC_SPAN),
        max_highlight_ratio=0.55,
    ),
    LocalizationBenchmarkCase(
        case_id="claim_partial_sentence",
        chunk_text=(
            "Decision trees split data using impurity measures such as entropy or gini. "
            "Each split chooses the feature that best separates classes."
        ),
        claim_text="impurity measures such as entropy",
        expect_precise_highlight=True,
        expect_statuses=(STATUS_EXACT, STATUS_SEMANTIC_SPAN, STATUS_SENTENCE, "fuzzy_compact", "normalized"),
        max_highlight_ratio=0.45,
    ),
    LocalizationBenchmarkCase(
        case_id="claim_two_nearby_sentences",
        chunk_text=(
            "Gradient descent minimizes loss. It updates weights iteratively. "
            "Football uses offside rules."
        ),
        claim_text="Gradient descent minimizes loss and updates weights iteratively.",
        expect_precise_highlight=True,
        expect_statuses=(STATUS_SENTENCE, STATUS_SEMANTIC_SPAN),
        max_highlight_ratio=0.65,
    ),
    LocalizationBenchmarkCase(
        case_id="chunk_with_unrelated_text",
        chunk_text=(
            "Photosynthesis converts light into chemical energy in plants. "
            "Supervised learning uses labeled examples for prediction tasks. "
            "The capital of France is Paris."
        ),
        claim_text="Supervised learning uses labeled examples for prediction.",
        expect_precise_highlight=True,
        expect_statuses=(STATUS_SENTENCE, STATUS_SEMANTIC_SPAN, STATUS_EXACT),
        max_highlight_ratio=0.45,
    ),
    LocalizationBenchmarkCase(
        case_id="multiple_topics_one_chunk",
        chunk_text=(
            "Neural networks stack layers of neurons. "
            "Basketball games have four quarters. "
            "Backpropagation computes gradients for training."
        ),
        claim_text="Backpropagation computes gradients for training.",
        expect_precise_highlight=True,
        expect_statuses=(STATUS_SENTENCE, STATUS_SEMANTIC_SPAN, STATUS_EXACT),
        max_highlight_ratio=0.40,
    ),
    LocalizationBenchmarkCase(
        case_id="quote_not_found",
        chunk_text="Entropy measures uncertainty in a dataset.",
        claim_text="Quantum computing uses qubits.",
        quote="Quantum computing uses qubits.",
        expect_precise_highlight=False,
        expect_unresolved=True,
    ),
    LocalizationBenchmarkCase(
        case_id="unsupported_claim",
        chunk_text="Linear regression fits a line to data points.",
        claim_text="Deep reinforcement learning won the 2010 World Cup.",
        expect_precise_highlight=False,
        expect_unresolved=True,
    ),
    LocalizationBenchmarkCase(
        case_id="bare_marker_claim_from_answer",
        chunk_text="Supervised learning uses labeled examples for training tasks.",
        claim_text="Supervised learning uses labeled data.",
        expect_precise_highlight=True,
        expect_statuses=(STATUS_SENTENCE, STATUS_SEMANTIC_SPAN, STATUS_EXACT),
        max_highlight_ratio=0.55,
    ),
]

HIGHLIGHT_BENCHMARK: list[HighlightBenchmarkCase] = [
    HighlightBenchmarkCase(
        case_id="exact_sentence",
        chunk_text="Supervised learning uses labeled examples. Unsupervised learning finds patterns without labels.",
        quote="Supervised learning uses labeled examples.",
        expect_highlight=True,
    ),
    HighlightBenchmarkCase(
        case_id="compact_whitespace",
        chunk_text="Entropy measures uncertainty in a dataset.",
        quote="Entropy  measures   uncertainty",
        expect_highlight=True,
        expect_match_types=("normalized", "fuzzy_compact", "exact", STATUS_EXACT),
    ),
    HighlightBenchmarkCase(
        case_id="quote_not_in_chunk",
        chunk_text="Gradient descent minimizes loss iteratively.",
        quote="Quantum computing uses qubits.",
        expect_in_chunk=False,
        expect_highlight=False,
        expect_match_types=("not_in_chunk", STATUS_UNRESOLVED),
    ),
    HighlightBenchmarkCase(
        case_id="short_quote_in_long_chunk",
        chunk_text=(
            "Decision trees split data using impurity measures such as entropy or gini. "
            "Each split chooses the feature that best separates classes."
        ),
        quote="impurity measures such as entropy",
        expect_highlight=True,
    ),
]

CLAIM_VERIFICATION_BENCHMARK: list[ClaimVerificationCase] = [
    ClaimVerificationCase(
        case_id="valid_marker",
        answer='Supervised learning uses labels.[E1:"labeled examples"]',
        chunk_text="Supervised learning uses labeled examples for training.",
        expect_valid_quote=True,
        expect_localization=True,
        expect_precise_highlight=True,
    ),
    ClaimVerificationCase(
        case_id="invalid_quote_stripped",
        answer='Supervised learning is magic.[E1:"invented quote text"]',
        chunk_text="Supervised learning uses labeled examples for training.",
        expect_valid_quote=False,
    ),
    ClaimVerificationCase(
        case_id="bare_marker_ok",
        answer="Supervised learning uses labeled data.[E1]",
        chunk_text="Supervised learning uses labeled examples for training.",
        expect_valid_quote=True,
        expect_localization=True,
        expect_precise_highlight=True,
    ),
    ClaimVerificationCase(
        case_id="paraphrase_bare_marker",
        answer="Models learn from labeled training data.[E1]",
        chunk_text="Supervised learning uses labeled examples for training tasks.",
        expect_valid_quote=True,
        expect_localization=True,
        expect_precise_highlight=False,
        notes="Paraphrase; localization may fallback when confidence is borderline.",
    ),
]


def dataset_stats() -> dict[str, Any]:
    return {
        "localization_cases": len(LOCALIZATION_BENCHMARK),
        "highlight_cases": len(HIGHLIGHT_BENCHMARK),
        "claim_cases": len(CLAIM_VERIFICATION_BENCHMARK),
    }
