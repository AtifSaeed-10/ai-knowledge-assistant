"""Reusable conversation-quality matrix. Behavior, not canned phrases."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from answer_prompt import (
    MISSING_EXAMPLE_PHRASE,
    MISSING_IN_DOCUMENT_PHRASE,
    build_answer_prompt,
)
from conversation_query import (
    INTENT_COMPARISON,
    INTENT_EXAMPLE,
    INTENT_HOW,
    INTENT_LISTING,
    INTENT_WHY,
    RELATION_NEW,
    analyze_turn,
    compose_followup_query,
    detect_intent,
)
from evidence_focus import (
    ROLE_MISMATCH,
    ROLE_SUPPORT,
    citation_allowlist,
    passage_taxonomy_role,
    subject_tokens_from_query,
)
from rag import ask_question


def _hist(*pairs: tuple[str, str]) -> list[dict]:
    history: list[dict] = []
    for user, assistant in pairs:
        history.append({"role": "user", "content": user})
        history.append({"role": "assistant", "content": assistant})
    return history


def _ml_hist() -> list[dict]:
    return _hist(
        (
            "What is supervised learning?",
            "Supervised learning trains models from labeled examples. "
            "Two common forms are classification and regression.",
        )
    )


def _retrieval(chunks: list[str], pages: list[int] | None = None, relevances: list[int] | None = None):
    pages = pages or [i + 1 for i in range(len(chunks))]
    relevances = relevances or [90] * len(chunks)
    return {
        "chunks": chunks,
        "distances": [0.2] * len(chunks),
        "metadata": [
            {
                "document_id": "doc-a",
                "filename": "ml.pdf",
                "page_number": page,
            }
            for page in pages
        ],
        "ids": [f"doc-a_{i}" for i in range(len(chunks))],
        "relevances": relevances,
        "reranker_scores": [2.0] * len(chunks),
        "rerank_fallback": False,
    }


class TestMatrixDirectAndFollowUps(unittest.TestCase):
    """A. Direct questions  B. Follow-up references  C. Presentation transforms."""

    def test_a_direct_self_contained_skips_rewrite(self):
        analysis = analyze_turn("What is entropy?", None)
        self.assertFalse(analysis.needs_rewrite)
        self.assertEqual(analysis.relation, RELATION_NEW)

    def test_b_pronoun_and_ordinal_bind_to_current_subject(self):
        for question in (
            "Why is it useful?",
            "How does it work?",
            "Explain the second one.",
        ):
            analysis = analyze_turn(question, _ml_hist())
            self.assertTrue(analysis.needs_rewrite, question)
            composed = compose_followup_query(question, _ml_hist(), analysis)
            self.assertIsNotNone(composed, question)
            self.assertNotEqual(composed.lower(), question.lower(), question)

    def test_c_presentation_transforms_keep_subject(self):
        for question in (
            "Explain it more simply.",
            "Make it more simple.",
            "Make it shorter.",
            "Give me the key points.",
            "Can you clarify?",
        ):
            analysis = analyze_turn(question, _ml_hist())
            self.assertTrue(analysis.needs_rewrite, question)
            self.assertNotEqual(analysis.relation, RELATION_NEW, question)
            composed = compose_followup_query(question, _ml_hist(), analysis)
            self.assertIsNotNone(composed, question)
            self.assertIn("supervised learning", composed.lower(), question)


class TestMatrixWhyHowExampleTaxonomy(unittest.TestCase):
    """D. Why/how  E. Examples  F. Taxonomy  G. Comparisons."""

    def test_d_why_prompt_rejects_definition_only_reasoning(self):
        analysis = analyze_turn("Why is it useful?", _ml_hist())
        prompt = build_answer_prompt(
            question="Why is it useful?",
            search_query="Why is supervised learning useful?",
            history=_ml_hist(),
            chunks=["Supervised learning is learning from labeled data."],
            metadata=[{"filename": "ml.pdf", "page_number": 2}],
            analysis=analysis,
            mode="normal",
        )
        self.assertIn("definition is not enough", prompt.lower())
        self.assertIn(MISSING_IN_DOCUMENT_PHRASE, prompt)
        self.assertEqual(analysis.intent, INTENT_WHY)

    def test_d_how_is_not_satisfied_by_a_name_only(self):
        analysis = analyze_turn("How does it work?", _ml_hist())
        self.assertEqual(analysis.intent, INTENT_HOW)
        prompt = build_answer_prompt(
            question="How does it work?",
            search_query="How does supervised learning work?",
            history=_ml_hist(),
            chunks=["Supervised learning uses labeled data."],
            metadata=[{"filename": "ml.pdf", "page_number": 2}],
            analysis=analysis,
        )
        self.assertIn("does not explain how", prompt.lower())

    def test_e_example_exists_uses_document_example_instruction(self):
        analysis = analyze_turn("Give me an example.", _ml_hist())
        self.assertEqual(analysis.intent, INTENT_EXAMPLE)
        prompt = build_answer_prompt(
            question="Give me an example.",
            search_query="example of supervised learning",
            history=_ml_hist(),
            chunks=["For example, predicting house prices from labeled sales data."],
            metadata=[{"filename": "ml.pdf", "page_number": 12}],
            analysis=analysis,
            evidence_notes="contains example language",
        )
        self.assertIn("comes from the document", prompt.lower())
        self.assertIn("house prices", prompt.lower())

    def test_e_example_missing_has_explicit_fallback_phrase(self):
        analysis = analyze_turn("Give me an example.", _ml_hist())
        prompt = build_answer_prompt(
            question="Give me an example.",
            search_query="example of supervised learning",
            history=_ml_hist(),
            chunks=["Supervised learning uses labeled data."],
            metadata=[{"filename": "ml.pdf", "page_number": 3}],
            analysis=analysis,
        )
        self.assertIn(MISSING_EXAMPLE_PHRASE, prompt)
        self.assertIn("Never fabricate an example", prompt)

    def test_f_parent_taxonomy_is_mismatch_for_child_types(self):
        parent = (
            "Machine learning can be classified into supervised, "
            "unsupervised, and reinforcement learning."
        )
        child = (
            "Supervised learning can be classified into classification "
            "and regression."
        )
        tokens = subject_tokens_from_query("types of supervised learning")
        self.assertEqual(passage_taxonomy_role(parent, tokens), ROLE_MISMATCH)
        self.assertEqual(passage_taxonomy_role(child, tokens), ROLE_SUPPORT)

        allow = citation_allowlist(
            [parent, child],
            "types of supervised learning",
            analyze_turn("What are the types of supervised learning?", None),
        )
        self.assertEqual(allow, {1})

    def test_f_parent_only_evidence_is_not_citable_as_child_types(self):
        parent = (
            "Machine learning can be classified into supervised, "
            "unsupervised, and reinforcement learning."
        )
        analysis = analyze_turn("What are the types of supervised learning?", None)
        self.assertEqual(analysis.intent, INTENT_LISTING)
        allow = citation_allowlist([parent], "types of supervised learning", analysis)
        self.assertEqual(allow, set())

        retrieval = _retrieval([parent], pages=[4], relevances=[92])
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value="I couldn't find that in the provided document.",
        ):
            result = ask_question(
                "What are the types of supervised learning?",
                None,
                ["doc-a"],
                generate=True,
            )
        self.assertEqual(result["sources"], [])
        self.assertIn("parent taxonomy", result["prompt"].lower())

    def test_g_comparison_intent_without_hardcoded_pair(self):
        self.assertEqual(
            detect_intent("What is the difference?"),
            INTENT_COMPARISON,
        )
        analysis = analyze_turn("What is the difference?", _ml_hist())
        self.assertTrue(analysis.needs_rewrite)
        composed = compose_followup_query(
            "What is the difference?",
            _ml_hist(),
            analysis,
        )
        self.assertIsNotNone(composed)
        lowered = composed.lower()
        self.assertTrue("classification" in lowered and "regression" in lowered)


class TestMatrixUnsupportedScopeCitations(unittest.TestCase):
    """H. Multi-part  I. Unsupported  J. Topic switch  K. Super Focused
    L. Citations  M. Overlap  N. Empty retrieval  O. Repeated questions."""

    def test_h_multi_part_marks_unsupported_parts(self):
        analysis = analyze_turn(
            "Explain clustering, list its types, and compare it with classification.",
            None,
        )
        prompt = build_answer_prompt(
            question="Explain clustering, list its types, and compare it with classification.",
            search_query="Explain clustering, list its types, and compare it with classification.",
            history=None,
            chunks=["Clustering groups unlabeled examples."],
            metadata=[{"filename": "ml.pdf", "page_number": 8}],
            analysis=analysis,
        )
        self.assertIn("multi-part", prompt.lower())
        self.assertIn("unsupported", prompt.lower())

    def test_i_related_but_insufficient_why_evidence_is_cautioned(self):
        analysis = analyze_turn(
            "Why is lower entropy better when choosing a split?",
            None,
        )
        self.assertEqual(analysis.intent, INTENT_WHY)
        prompt = build_answer_prompt(
            question="Why is lower entropy better when choosing a split?",
            search_query="Why is lower entropy better when choosing a split?",
            history=None,
            chunks=["Entropy is a measure of impurity in a dataset."],
            metadata=[{"filename": "ml.pdf", "page_number": 9}],
            analysis=analysis,
            evidence_notes="may mention the topic without explaining why.",
        )
        self.assertIn("without explaining why", prompt.lower())
        self.assertIn("do not upgrade a definition", prompt.lower())

    def test_j_topic_switch_does_not_inherit_old_subject(self):
        analysis = analyze_turn("What is a red card in football?", _ml_hist())
        self.assertFalse(analysis.needs_rewrite)
        self.assertEqual(analysis.relation, RELATION_NEW)
        composed = compose_followup_query(
            "What is a red card in football?",
            _ml_hist(),
            analysis,
        )
        self.assertIsNone(composed)

        with patch(
            "rag.retrieve_candidates",
            return_value=_retrieval(["A red card is a sending-off."], [47]),
        ) as mock_retrieve, patch(
            "rag.rewrite_query",
            return_value="SHOULD NOT BE USED",
        ) as mock_rewrite, patch(
            "rag.generate_response",
            return_value="A red card dismisses a player.",
        ):
            result = ask_question(
                "What is a red card in football?",
                _ml_hist(),
                ["doc-a"],
                generate=True,
            )
        mock_rewrite.assert_not_called()
        self.assertEqual(mock_retrieve.call_args_list[0].args[0], "What is a red card in football?")
        self.assertNotIn("SHOULD NOT BE USED", result["prompt"])

    def test_k_super_focused_forbids_outside_knowledge(self):
        analysis = analyze_turn("Give me an example.", _ml_hist())
        prompt = build_answer_prompt(
            question="Give me an example.",
            search_query="example of supervised learning",
            history=_ml_hist(),
            chunks=["Supervised learning uses labeled data."],
            metadata=[{"filename": "ml.pdf", "page_number": 3}],
            analysis=analysis,
            mode="super_focused",
        )
        self.assertIn("SUPER FOCUSED", prompt)
        self.assertIn("world knowledge", prompt.lower())

    def test_l_citations_prefer_supporting_example_passage(self):
        retrieval = _retrieval(
            [
                "Supervised learning uses labeled data.",
                "For example, predicting house prices from labeled sales.",
            ],
            pages=[3, 12],
            relevances=[88, 86],
        )
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value="The document's example is house-price prediction.",
        ):
            result = ask_question(
                "Give me an example.",
                _ml_hist(),
                ["doc-a"],
                generate=True,
            )
        pages = [source["page"] for source in result["sources"]]
        self.assertEqual(pages, [12])

    def test_m_overlapping_parent_and_child_does_not_cite_parent_for_types(self):
        retrieval = _retrieval(
            [
                "Machine learning can be classified into supervised, unsupervised, and reinforcement learning.",
                "Decision trees split nodes using information gain.",
            ],
            pages=[5, 6],
            relevances=[91, 70],
        )
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value="I couldn't find that in the provided document.",
        ):
            result = ask_question(
                "What are the types of supervised learning?",
                None,
                ["doc-a"],
                generate=True,
            )
        self.assertEqual(result["sources"], [])

    def test_n_empty_retrieval_keeps_unanswerable_contract(self):
        empty = _retrieval([])
        empty["chunks"] = []
        empty["metadata"] = []
        empty["ids"] = []
        empty["relevances"] = []
        empty["distances"] = []
        empty["reranker_scores"] = []
        with patch("rag.retrieve_candidates", return_value=empty):
            result = ask_question("Who won the World Cup?", None, ["doc-a"], generate=True)
        self.assertEqual(result["sources"], [])
        self.assertIn("No relevant information", result["answer"])

    def test_o_repeated_self_contained_question_does_not_rewrite(self):
        history = _ml_hist() + [
            {"role": "user", "content": "What is supervised learning?"},
            {"role": "assistant", "content": "It learns from labeled data."},
        ]
        analysis = analyze_turn("What is supervised learning?", history)
        self.assertFalse(analysis.needs_rewrite)


class TestMatrixAdversarialRelatedEvidence(unittest.TestCase):
    def test_entropy_definition_is_not_split_quality_reasoning(self):
        tokens = subject_tokens_from_query(
            "Why is lower entropy better when choosing a decision-tree split?"
        )
        definition = "Entropy is a measure of impurity or uncertainty."
        from evidence_focus import passage_reason_role

        role = passage_reason_role(definition, tokens, how=False)
        self.assertNotEqual(role, ROLE_SUPPORT)

    def test_history_is_not_treated_as_evidence_in_prompt(self):
        analysis = analyze_turn("Give another example.", _ml_hist())
        prompt = build_answer_prompt(
            question="Give another example.",
            search_query="another example of supervised learning",
            history=_ml_hist(),
            chunks=["No example text here, only a definition of labels."],
            metadata=[{"filename": "ml.pdf", "page_number": 1}],
            analysis=analysis,
        )
        self.assertIn("reference resolution only", prompt.lower())
        self.assertIn("not evidence", prompt.lower())
        self.assertIn("Never fabricate an example", prompt)

    def test_prompt_does_not_ask_model_to_echo_passage_numbers(self):
        prompt = build_answer_prompt(
            question="What is entropy?",
            search_query="What is entropy?",
            history=None,
            chunks=["Entropy measures uncertainty."],
            metadata=[{"filename": "ml.pdf", "page_number": 4}],
            analysis=analyze_turn("What is entropy?", None),
        )
        self.assertNotIn("Passage 1", prompt)
        self.assertIn("Source: ml.pdf, p. 4", prompt)
        self.assertIn("Do not mention source labels", prompt)


if __name__ == "__main__":
    unittest.main()
