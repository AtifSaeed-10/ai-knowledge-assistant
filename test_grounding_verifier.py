"""Item 7: block blanket refusals when supporting text is already in context."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from answer_formatter import polish_answer_text
from answer_prompt import MISSING_IN_DOCUMENT_PHRASE, build_answer_prompt
from conversation_query import analyze_turn
from grounding_verifier import (
    EVIDENCE_PRESENT_LEAD,
    find_context_support,
    is_blanket_refusal,
    verify_and_repair_refusal,
)
from rag import ask_question


NOTICE_CHUNK = (
    "Either party may terminate the agreement by giving thirty days written "
    "notice to the other party's registered office."
)
STAGES_CHUNK = (
    "Onboarding has four stages: paperwork, workstation setup, mentor "
    "assignment, and a 30-day review meeting with the hiring manager."
)
TAXONOMY_CHUNK = (
    "Machine learning can be classified into supervised, unsupervised, and "
    "reinforcement learning."
)
LEAVE_CHUNK = (
    "Employees accrue twenty days of paid leave each calendar year. Unused "
    "leave may be carried over up to five days. Requests must be submitted "
    "two weeks in advance except for illness."
)
KITCHEN_CHUNK = (
    "The office kitchen is stocked with tea, coffee, and biscuits for staff."
)


def _source(chunk_id: str, text: str, *, page: int, evidence_id: str, relevance: int = 80):
    return {
        "chunk_id": chunk_id,
        "text": text,
        "snippet": text[:80],
        "page": page,
        "evidence_id": evidence_id,
        "relevance": relevance,
        "document_id": "handbook",
        "filename": "staff_handbook.pdf",
    }


def _retrieval(chunks: list[str], pages: list[int], relevances: list[int], ids: list[str]):
    return {
        "chunks": chunks,
        "distances": [0.2] * len(chunks),
        "metadata": [
            {
                "document_id": "handbook",
                "filename": "staff_handbook.pdf",
                "page_number": page,
            }
            for page in pages
        ],
        "ids": ids,
        "relevances": relevances,
        "reranker_scores": [1.0] * len(chunks),
        "citation_eligible": [rel >= 30 for rel in relevances],
        "rerank_fallback": False,
    }


class TestBlanketRefusal(unittest.TestCase):
    def test_short_not_found_is_blanket(self):
        self.assertTrue(is_blanket_refusal(MISSING_IN_DOCUMENT_PHRASE))

    def test_partial_answer_with_missing_clause_is_not_blanket(self):
        answer = (
            "Paid leave accrues at twenty days per year and unused days may "
            "carry over up to five. The passages do not describe parental leave "
            "or unpaid leave options, so those parts could not be confirmed."
        )
        self.assertFalse(is_blanket_refusal(answer))


class TestContextSupport(unittest.TestCase):
    def test_notice_clause_supports_notice_question(self):
        hit = find_context_support(
            "How much notice is required to end the agreement?",
            sources=[_source("h12", NOTICE_CHUNK, page=12, evidence_id="E1")],
        )
        self.assertTrue(hit.supported)
        self.assertEqual(hit.evidence_id, "E1")

    def test_kitchen_chunk_does_not_support_world_cup(self):
        hit = find_context_support(
            "Who won the World Cup?",
            sources=[_source("h40", KITCHEN_CHUNK, page=40, evidence_id="E2", relevance=8)],
        )
        self.assertFalse(hit.supported)

    def test_listing_mismatch_is_not_support(self):
        analysis = analyze_turn("What are the types of supervised learning?", None)
        hit = find_context_support(
            "What are the types of supervised learning?",
            sources=[_source("ml5", TAXONOMY_CHUNK, page=5, evidence_id="E1")],
            analysis=analysis,
        )
        self.assertFalse(hit.supported)

    def test_listing_of_named_stages_is_support(self):
        analysis = analyze_turn("What are the four stages of onboarding?", None)
        hit = find_context_support(
            "What are the four stages of onboarding?",
            sources=[_source("h9", STAGES_CHUNK, page=9, evidence_id="E1")],
            analysis=analysis,
        )
        self.assertTrue(hit.supported)

    def test_summary_intent_treats_passages_as_enough_to_synthesize(self):
        analysis = analyze_turn("Summarize the leave policy.", None)
        hit = find_context_support(
            "Summarize the leave policy.",
            sources=[_source("h20", LEAVE_CHUNK, page=20, evidence_id="E1")],
            analysis=analysis,
        )
        self.assertTrue(hit.supported)
        self.assertEqual(hit.reason, "synthesis_context")


class TestVerifyAndRepair(unittest.TestCase):
    def test_unsupported_refusal_is_kept(self):
        repaired, meta = verify_and_repair_refusal(
            MISSING_IN_DOCUMENT_PHRASE,
            question="Who won the World Cup?",
            sources=[_source("h40", KITCHEN_CHUNK, page=40, evidence_id="E2", relevance=4)],
        )
        self.assertEqual(repaired, MISSING_IN_DOCUMENT_PHRASE)
        self.assertEqual(meta["action"], "keep")

    def test_supported_refusal_retries_then_keeps_retry(self):
        retried = (
            "Either party may end the agreement with thirty days written notice."
        )

        def generate_fn(prompt: str) -> str:
            self.assertIn("grounding check", prompt)
            return retried

        repaired, meta = verify_and_repair_refusal(
            MISSING_IN_DOCUMENT_PHRASE,
            question="How much notice is required to end the agreement?",
            prompt="base prompt",
            sources=[_source("h12", NOTICE_CHUNK, page=12, evidence_id="E1")],
            generate_fn=generate_fn,
        )
        self.assertEqual(repaired, retried)
        self.assertEqual(meta["action"], "retry")

    def test_supported_refusal_falls_back_to_excerpt_not_invention(self):
        repaired, meta = verify_and_repair_refusal(
            MISSING_IN_DOCUMENT_PHRASE,
            question="How much notice is required to end the agreement?",
            prompt="base prompt",
            sources=[_source("h12", NOTICE_CHUNK, page=12, evidence_id="E1")],
            generate_fn=lambda _prompt: MISSING_IN_DOCUMENT_PHRASE,
        )
        self.assertEqual(meta["action"], "extractive")
        self.assertIn(EVIDENCE_PRESENT_LEAD, repaired)
        self.assertIn("thirty days", repaired.lower())
        self.assertIn("[E1]", repaired)
        self.assertNotEqual(repaired, MISSING_IN_DOCUMENT_PHRASE)
        polished = polish_answer_text(repaired)
        self.assertIn("thirty days", polished.lower())
        self.assertIn("[E1]", polished)

    def test_empty_context_keeps_refusal(self):
        repaired, meta = verify_and_repair_refusal(
            MISSING_IN_DOCUMENT_PHRASE,
            question="Summarize chapter 1.",
            sources=[],
            analysis=analyze_turn("Summarize chapter 1.", None),
        )
        self.assertEqual(repaired, MISSING_IN_DOCUMENT_PHRASE)
        self.assertEqual(meta["action"], "keep")


class TestPromptAntiRefusal(unittest.TestCase):
    def test_summary_prompt_tells_model_to_synthesize(self):
        analysis = analyze_turn("Summarize the leave policy.", None)
        prompt = build_answer_prompt(
            question="Summarize the leave policy.",
            search_query="leave policy",
            history=None,
            chunks=[LEAVE_CHUNK],
            metadata=[{"filename": "staff_handbook.pdf", "page_number": 20}],
            evidence_ids=["E1"],
            analysis=analysis,
        )
        lowered = prompt.lower()
        self.assertIn("synthesize", lowered)
        self.assertIn("summary", lowered)


class TestAskQuestionAntiRefusal(unittest.TestCase):
    def test_grounded_notice_refusal_is_replaced(self):
        retrieval = _retrieval(
            [NOTICE_CHUNK, KITCHEN_CHUNK],
            [12, 40],
            [88, 9],
            ["handbook_12", "handbook_40"],
        )
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value=MISSING_IN_DOCUMENT_PHRASE,
        ):
            result = ask_question(
                "How much notice is required to end the agreement?",
                None,
                ["handbook"],
                generate=True,
            )
        self.assertNotEqual(result["answer"], MISSING_IN_DOCUMENT_PHRASE)
        self.assertIn("thirty days", result["answer"].lower())
        self.assertTrue(result["sources"])

    def test_summary_refusal_is_replaced_when_passages_exist(self):
        retrieval = _retrieval(
            [LEAVE_CHUNK],
            [20],
            [90],
            ["handbook_20"],
        )
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value=MISSING_IN_DOCUMENT_PHRASE,
        ):
            result = ask_question(
                "Summarize the leave policy.",
                None,
                ["handbook"],
                generate=True,
            )
        self.assertNotEqual(result["answer"], MISSING_IN_DOCUMENT_PHRASE)
        self.assertIn("twenty days", result["answer"].lower())
        self.assertTrue(result["sources"])

    def test_simplify_followup_refusal_is_replaced_when_topic_passages_exist(self):
        history = [
            {"role": "user", "content": "What is supervised learning?"},
            {
                "role": "assistant",
                "content": "Supervised learning trains models from labeled examples.",
            },
        ]
        retrieval = _retrieval(
            [
                "Supervised learning trains models from labeled examples. "
                "Classification and regression are common forms of this approach."
            ],
            [3],
            [90],
            ["ml_3"],
        )
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value=MISSING_IN_DOCUMENT_PHRASE,
        ):
            result = ask_question(
                "make it more simple",
                history,
                ["handbook"],
                generate=True,
            )
        self.assertNotEqual(result["answer"], MISSING_IN_DOCUMENT_PHRASE)
        self.assertTrue(result["sources"])
        self.assertTrue(
            "labeled" in result["answer"].lower()
            or "supervised" in result["answer"].lower()
        )

    def test_listing_mismatch_refusal_is_kept(self):
        retrieval = _retrieval(
            [TAXONOMY_CHUNK],
            [5],
            [91],
            ["ml_5"],
        )
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value=MISSING_IN_DOCUMENT_PHRASE,
        ):
            result = ask_question(
                "What are the types of supervised learning?",
                None,
                ["doc-a"],
                generate=True,
            )
        self.assertEqual(result["answer"], MISSING_IN_DOCUMENT_PHRASE)
        self.assertEqual(result["sources"], [])

    def test_off_topic_world_cup_refusal_is_kept(self):
        retrieval = _retrieval(
            [KITCHEN_CHUNK],
            [40],
            [4],
            ["handbook_40"],
        )
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value=MISSING_IN_DOCUMENT_PHRASE,
        ):
            result = ask_question(
                "Who won the World Cup?",
                None,
                ["handbook"],
                generate=True,
            )
        self.assertEqual(result["answer"], MISSING_IN_DOCUMENT_PHRASE)
        self.assertEqual(result["sources"], [])


if __name__ == "__main__":
    unittest.main()
