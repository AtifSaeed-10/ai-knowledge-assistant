"""Web fallback — document first, trusted web only when the files cannot answer."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from test_support import api_client

from backend import app
from evidence_state import looks_like_evidence_refusal
from memory.store import delete_conversation
from web_fallback.coverage import (
    passages_are_off_topic,
    passages_miss_question,
    short_document_scope_note,
)
from web_fallback.decision import (
    ACTION_CONTINUE,
    ACTION_DOCUMENT,
    ACTION_WEB,
    REASON_DOC_INSUFFICIENT_POST_LLM,
    REASON_DOC_INSUFFICIENT_PRE_LLM,
    REASON_DOC_OFF_TOPIC,
    REASON_DOC_SUFFICIENT,
    REASON_WEB_SKIPPED_DISABLED,
    REASON_WEB_SKIPPED_TOGGLE_OFF,
    decide_web_after_answer,
    decide_web_fallback,
    is_document_gap_answer,
    is_pre_llm_insufficient,
)
from web_fallback.orchestrator import (
    combine_document_and_web_answer,
    execute_web_fallback,
    merge_answer_sources,
    search_web,
)
from web_fallback.prompt import (
    WEB_GAP_PREVIEW_ANSWER,
    WEB_PREVIEW_ANSWER,
    WEB_UNAVAILABLE_ANSWER,
    build_web_gap_prompt,
    build_web_prompt,
)
from web_fallback.provider import TavilyWebSearchProvider
from web_fallback.types import WebHit


def _empty_retrieval():
    return {
        "chunks": [],
        "distances": [],
        "metadata": [],
        "ids": [],
        "relevances": [],
        "reranker_scores": [],
        "rerank_fallback": False,
    }


def _hit_retrieval(document_id="doc-a"):
    return {
        "chunks": ["Supervised learning uses labeled data."],
        "distances": [0.2],
        "metadata": [
            {
                "document_id": document_id,
                "filename": "ml.pdf",
                "page_number": 1,
            }
        ],
        "ids": [f"{document_id}_0"],
        "relevances": [90],
        "reranker_scores": [2.0],
        "rerank_fallback": False,
    }


def _related_gap_retrieval(document_id="doc-a"):
    """Same subject as the question, but missing the asked later period."""
    return {
        "chunks": [
            "The 1990s amendment of the offside law says a player is in an "
            "offside position if nearer to the opponents' goal line than both "
            "the ball and the second-last opponent."
        ],
        "distances": [0.2],
        "metadata": [
            {
                "document_id": document_id,
                "filename": "rules.pdf",
                "page_number": 1,
            }
        ],
        "ids": [f"{document_id}_0"],
        "relevances": [90],
        "reranker_scores": [2.0],
        "rerank_fallback": False,
    }


def _off_topic_retrieval(document_id="doc-a"):
    return {
        "chunks": [
            "Naval campaigns and occupation policy after a 20th century war "
            "in Europe. The files discuss aftermath and reconstruction."
        ],
        "distances": [0.2],
        "metadata": [
            {
                "document_id": document_id,
                "filename": "history.pdf",
                "page_number": 4,
            }
        ],
        "ids": [f"{document_id}_0"],
        "relevances": [90],
        "reranker_scores": [2.0],
        "rerank_fallback": False,
    }


DOC_GAP_ANSWER = (
    "I couldn't find information in the provided document regarding the 2018 amendment. "
    "The provided excerpts do not extend to that later revision. "
    "What the document does cover is the 1990s wording of the law: a player is in an "
    "offside position if nearer to the opponents' goal line than both the ball and the "
    "second-last opponent, with the referee judging the moment the ball is played. [E1]"
)
WEB_GAP_FILL = (
    "The 2018 revision clarified that attacking players are judged at the moment the ball is played."
)


def _trusted_web_hits():
    return [
        WebHit(
            title="Laws of the Game",
            url="https://www.theifab.com/news/2018-law-changes",
            snippet="The 2018 revision clarified the moment of judgement.",
            domain="theifab.com",
            provider="tavily",
            preview=False,
            tier="t1",
        )
    ]


def _generate_doc_or_web(prompt: str) -> str:
    text = prompt or ""
    if "Web passages:" in text or "numbered web passages" in text:
        return WEB_GAP_FILL
    return DOC_GAP_ANSWER


class TestWebFallbackDecision(unittest.TestCase):
    def test_prompt_means_documents_were_enough(self):
        action, reason = decide_web_fallback(
            user_enabled=True,
            document_result={"prompt": "use E1", "answer": None},
            server_enabled=True,
        )
        self.assertEqual(action, ACTION_CONTINUE)
        self.assertEqual(reason, REASON_DOC_SUFFICIENT)
        self.assertFalse(is_pre_llm_insufficient({"prompt": "use E1"}))

    def test_empty_retrieval_is_insufficient(self):
        result = {
            "prompt": None,
            "answer": "No relevant information found in the document.",
            "sources": [],
        }
        self.assertTrue(is_pre_llm_insufficient(result))
        self.assertTrue(looks_like_evidence_refusal(result["answer"]))

        action, reason = decide_web_fallback(
            user_enabled=True,
            document_result=result,
            server_enabled=True,
        )
        self.assertEqual(action, ACTION_WEB)
        self.assertEqual(reason, REASON_DOC_INSUFFICIENT_PRE_LLM)

    def test_toggle_off_does_not_search(self):
        result = {
            "prompt": None,
            "answer": "No relevant information found in the document.",
        }
        action, reason = decide_web_fallback(
            user_enabled=False,
            document_result=result,
            server_enabled=True,
        )
        self.assertEqual(action, ACTION_DOCUMENT)
        self.assertEqual(reason, REASON_WEB_SKIPPED_TOGGLE_OFF)

    def test_server_flag_blocks_web(self):
        result = {
            "prompt": None,
            "answer": "No relevant information found in the document.",
        }
        action, reason = decide_web_fallback(
            user_enabled=True,
            document_result=result,
            server_enabled=False,
        )
        self.assertEqual(action, ACTION_DOCUMENT)
        self.assertEqual(reason, REASON_WEB_SKIPPED_DISABLED)

    def test_small_talk_is_not_a_web_trigger(self):
        result = {
            "prompt": None,
            "answer": "Hello. Ask me anything about your PDFs and I will answer with the page it came from.",
            "sources": [],
        }
        self.assertFalse(is_pre_llm_insufficient(result))
        action, reason = decide_web_fallback(
            user_enabled=True,
            document_result=result,
            server_enabled=True,
        )
        self.assertEqual(action, ACTION_DOCUMENT)
        self.assertEqual(reason, REASON_DOC_SUFFICIENT)

    def test_off_topic_pages_search_before_document_generate(self):
        result = {
            "prompt": "use E1",
            "sources": [{"filename": "history.pdf"}],
            "recall_candidates": [
                {
                    "filename": "history.pdf",
                    "text": "Naval campaigns and occupation policy in Europe.",
                }
            ],
        }
        action, reason = decide_web_fallback(
            user_enabled=True,
            document_result=result,
            server_enabled=True,
            question="who won the world cup in 2022",
        )
        self.assertEqual(action, ACTION_WEB)
        self.assertEqual(reason, REASON_DOC_OFF_TOPIC)

    def test_related_pages_search_when_the_asked_fact_is_missing(self):
        blob = (
            "The 1990s amendment of the offside law says a player is in an "
            "offside position if nearer to the opponents' goal line."
        )
        result = {
            "prompt": "use E1",
            "recall_candidates": [{"filename": "rules.pdf", "text": blob}],
        }
        action, reason = decide_web_fallback(
            user_enabled=True,
            document_result=result,
            server_enabled=True,
            question="What changed in the 2018 amendment?",
        )
        self.assertEqual(action, ACTION_WEB)
        self.assertEqual(reason, REASON_DOC_INSUFFICIENT_PRE_LLM)
        self.assertFalse(
            passages_are_off_topic("What changed in the 2018 amendment?", blob)
        )
        self.assertTrue(
            passages_miss_question("What changed in the 2018 amendment?", blob)
        )

    def test_off_topic_toggle_off_stays_on_documents(self):
        result = {
            "prompt": "use E1",
            "recall_candidates": [
                {"text": "Naval campaigns and occupation policy in Europe."}
            ],
        }
        action, reason = decide_web_fallback(
            user_enabled=False,
            document_result=result,
            server_enabled=True,
            question="who won the world cup in 2022",
        )
        self.assertEqual(action, ACTION_CONTINUE)
        self.assertEqual(reason, REASON_DOC_SUFFICIENT)


class TestPassageCoverage(unittest.TestCase):
    def test_unrelated_pages_are_off_topic(self):
        war = (
            "The retrieved pages describe naval campaigns, occupation policy, "
            "and the aftermath of a 20th century war in Europe."
        )
        self.assertTrue(passages_are_off_topic("who won the world cup in 2022", war))
        self.assertTrue(passages_miss_question("who won the world cup in 2022", war))

    def test_same_subject_later_period_is_a_gap_not_off_topic(self):
        early = (
            "The files cover the group, party organisation and agitation in 1919. "
            "They mention hostile newspaper articles from that year."
        )
        question = "what happened to the group in ww2"
        self.assertFalse(passages_are_off_topic(question, early))
        self.assertTrue(passages_miss_question(question, early))

    def test_matching_pages_are_on_topic(self):
        football = (
            "Argentina won the 2022 FIFA World Cup in Qatar. "
            "Lionel Messi lifted the trophy after the final in Lusail."
        )
        self.assertFalse(passages_are_off_topic("who won the world cup in 2022", football))
        self.assertFalse(passages_miss_question("who won the world cup in 2022", football))

    def test_pronouns_do_not_make_an_unrelated_pdf_look_on_topic(self):
        ml = (
            "You can use a similar method to train computers. "
            "Supervised learning uses labeled examples and cluster centroids."
        )
        question = "Can you tell me who is john cena"
        self.assertTrue(passages_are_off_topic(question, ml))
        self.assertTrue(passages_miss_question(question, ml))

    def test_generic_model_word_does_not_keep_an_unrelated_pdf(self):
        ml = (
            "You can use a similar method to train computers. "
            "A probabilistic classifier is a model that predicts a distribution."
        )
        question = "what is the chatgpt latest model astra"
        self.assertTrue(passages_are_off_topic(question, ml))
        self.assertTrue(passages_miss_question(question, ml))

    def test_list_question_words_do_not_keep_an_unrelated_pdf(self):
        ml = (
            "The last section covers nearest neighbour methods. "
            "A prime number example is not required for distance ranking."
        )
        question = "who are the pakistan last 5 prime ministers"
        self.assertTrue(passages_are_off_topic(question, ml))
        self.assertTrue(passages_miss_question(question, ml))

    def test_generic_price_word_does_not_keep_an_unrelated_pdf(self):
        ml = (
            "For example, predicting house prices from labeled sales data. "
            "Supervised learning uses a training set of examples."
        )
        self.assertTrue(
            passages_are_off_topic("what is bitcoin latest price", ml)
        )
        self.assertTrue(
            passages_are_off_topic("bitcoin latest price", ml)
        )

    def test_scope_note_names_the_file(self):
        note = short_document_scope_note(
            {"sources": [{"filename": "history.pdf"}]}
        )
        self.assertIn("don't cover this question", note)
        self.assertIn("history.pdf", note)


class TestWebFallbackExecute(unittest.TestCase):
    def test_preview_hits_do_not_call_the_llm(self):
        hits = [
            WebHit(
                title="Preview",
                url="https://example.com/preview",
                snippet="Development only.",
                domain="example.com",
                preview=True,
            )
        ]

        def boom(_prompt: str) -> str:
            raise AssertionError("preview hits must not generate")

        result = execute_web_fallback(
            "What is offside?",
            search_fn=lambda _query: hits,
            generate_fn=boom,
        )
        self.assertEqual(result.answer, WEB_PREVIEW_ANSWER)
        self.assertEqual(len(result.sources), 1)
        self.assertEqual(result.sources[0]["kind"], "web")
        self.assertEqual(result.sources[0]["evidence_id"], "W1")
        self.assertTrue(result.preview)

    def test_no_hits_fail_closed(self):
        result = execute_web_fallback(
            "What is offside?",
            search_fn=lambda _query: [],
        )
        self.assertEqual(result.answer, WEB_UNAVAILABLE_ANSWER)
        self.assertEqual(result.sources, [])

    def test_web_prompt_never_asks_for_pdf_markers(self):
        prompt = build_web_prompt(
            "What is offside?",
            [
                WebHit(
                    title="IFAB",
                    url="https://www.theifab.com/laws",
                    snippet="A player is in an offside position if...",
                    domain="theifab.com",
                    preview=False,
                    tier="t1",
                )
            ],
        )
        self.assertIn("[W1]", prompt)
        self.assertIn("Do not use PDF evidence markers", prompt)
        self.assertIn("theifab.com", prompt)
        self.assertIn("official source", prompt)
        self.assertIn("Do not put [W1]", prompt)
        self.assertIn("Lead with the fact", prompt)
        self.assertIn("Do not open with a document-miss apology", prompt)

    def test_web_answer_strips_source_markers(self):
        from web_fallback.orchestrator import finalize_web_answer

        cleaned = finalize_web_answer(
            "GPT-6 Astra launched in 2026 [W2][W5]. It is OpenAI's latest model [W3]."
        )
        self.assertEqual(
            cleaned,
            "GPT-6 Astra launched in 2026. It is OpenAI's latest model.",
        )
        self.assertNotIn("[W", cleaned)

    def test_live_hits_generate_from_passages(self):
        hits = [
            WebHit(
                title="Laws of the Game",
                url="https://www.theifab.com/laws/offside",
                snippet="A player is in an offside position if nearer to the opponents' goal line than both the ball and the second-last opponent.",
                domain="theifab.com",
                provider="tavily",
                preview=False,
                tier="t1",
            )
        ]
        prompts: list[str] = []

        def generate(prompt: str) -> str:
            prompts.append(prompt)
            return "A player is offside when nearer the goal than the ball and the second-last opponent."

        result = execute_web_fallback(
            "What is the offside rule?",
            search_fn=lambda _query: hits,
            generate_fn=generate,
        )
        self.assertFalse(result.preview)
        self.assertIn("offside", result.answer.lower())
        self.assertEqual(len(prompts), 1)
        self.assertIn("[W1]", prompts[0])
        self.assertIn("theifab.com", prompts[0])
        self.assertEqual(result.sources[0]["tier"], "t1")

    def test_live_hits_can_defer_generation_for_streaming(self):
        hits = [
            WebHit(
                title="Laws of the Game",
                url="https://www.theifab.com/laws/offside",
                snippet="A player is in an offside position if...",
                domain="theifab.com",
                provider="tavily",
                preview=False,
                tier="t1",
            )
        ]

        def boom(_prompt: str) -> str:
            raise AssertionError("stream path must not generate up front")

        result = execute_web_fallback(
            "What is the offside rule?",
            search_fn=lambda _query: hits,
            generate_fn=boom,
            generate=False,
        )
        self.assertEqual(result.answer, "")
        self.assertTrue(result.prompt)
        self.assertIn("[W1]", result.prompt)

    def test_gap_prompt_asks_to_fill_only_the_missing_part(self):
        document_answer = (
            "I couldn't find information in the provided document regarding the 2018 amendment. "
            "The document covers the 1990s wording of the law [E1]."
        )
        prompt = build_web_gap_prompt(
            "What changed in the 2018 amendment?",
            document_answer,
            [
                WebHit(
                    title="IFAB",
                    url="https://www.theifab.com/laws",
                    snippet="The 2018 revision clarified the moment of judgement.",
                    domain="theifab.com",
                    preview=False,
                    tier="t1",
                )
            ],
        )
        self.assertIn("Answer ONLY the part", prompt)
        self.assertIn("2018 amendment", prompt)
        self.assertIn("1990s wording", prompt)
        self.assertIn("[W1]", prompt)
        self.assertIn("Do not mention the web", prompt)

    def test_gap_preview_does_not_replace_the_document_answer(self):
        hits = [
            WebHit(
                title="Preview",
                url="https://example.com/preview",
                snippet="Development only.",
                domain="example.com",
                preview=True,
            )
        ]
        document_answer = (
            "I couldn't find that in the provided document. "
            "The files only cover the 1990s wording [E1]."
        )
        result = execute_web_fallback(
            "What changed in 2018?",
            search_fn=lambda _query: hits,
            document_answer=document_answer,
        )
        self.assertEqual(result.answer, WEB_GAP_PREVIEW_ANSWER)
        combined = combine_document_and_web_answer(document_answer, result.answer)
        self.assertIn("1990s wording", combined)
        self.assertIn("preview", combined.lower())
        self.assertTrue(combined.startswith("I couldn't find"))

    def test_miss_only_document_note_does_not_replace_a_web_answer(self):
        miss = "I couldn't find that in the provided document."
        web = "Shehbaz Sharif, Anwaar-ul-Haq Kakar, Shehbaz Sharif, Imran Khan, and Nasirul Mulk."
        combined = combine_document_and_web_answer(miss, web)
        self.assertEqual(combined, web)
        self.assertNotIn("couldn't find", combined.lower())


class TestSearchQueries(unittest.TestCase):
    def test_list_questions_add_a_list_of_query(self):
        from web_fallback.search_query import looks_like_list_question, search_queries

        question = "Can you tell me the names of NBA winners from 2010-2026 ranking"
        self.assertTrue(looks_like_list_question(question))
        queries = search_queries(question)
        self.assertTrue(any(item.lower().startswith("list of ") for item in queries))
        self.assertTrue(any("NBA" in item or "nba" in item.lower() for item in queries))

    def test_recency_questions_search_the_current_year_not_a_year_span(self):
        from datetime import datetime, timezone

        from web_fallback.search_query import (
            looks_like_recency_question,
            search_queries,
        )

        question = "what is the score of barcelona's last match"
        self.assertTrue(looks_like_recency_question(question))
        self.assertFalse(
            looks_like_recency_question("who are the last 5 prime ministers")
        )
        self.assertFalse(
            looks_like_recency_question("NBA winners from 2010-2026 ranking")
        )
        year = str(datetime.now(timezone.utc).year)
        queries = search_queries(question)
        self.assertTrue(any(year in item for item in queries))
        self.assertTrue(any("match" in item.lower() for item in queries))
        self.assertLessEqual(len(queries), 3)


class TestPostLlmGapDecision(unittest.TestCase):
    def test_related_pages_with_missing_fact_is_a_gap(self):
        answer = (
            "I couldn't find information in the provided document regarding the 2018 amendment. "
            "The provided excerpts do not extend to that later revision. "
            "The document covers the 1990s wording of the law."
        )
        self.assertTrue(is_document_gap_answer(answer))
        should, reason = decide_web_after_answer(
            user_enabled=True,
            answer=answer,
            server_enabled=True,
        )
        self.assertTrue(should)
        self.assertEqual(reason, REASON_DOC_INSUFFICIENT_POST_LLM)

    def test_paraphrased_information_refusal_still_triggers_web(self):
        answer = "I don't have that information in the provided documents."
        self.assertTrue(is_document_gap_answer(answer))
        should, reason = decide_web_after_answer(
            user_enabled=True,
            answer=answer,
            server_enabled=True,
        )
        self.assertTrue(should)
        self.assertEqual(reason, REASON_DOC_INSUFFICIENT_POST_LLM)

    def test_curly_apostrophe_refusal_still_triggers_web(self):
        answer = (
            "I couldn\u2019t find information in the provided document about who won "
            "the 2022 football World Cup.\n\n"
            "The provided passages focus exclusively on an earlier period. "
            "The text does not contain any details regarding sports events or World Cup tournaments."
        )
        self.assertTrue(looks_like_evidence_refusal(answer))
        self.assertTrue(is_document_gap_answer(answer))
        should, reason = decide_web_after_answer(
            user_enabled=True,
            answer=answer,
            server_enabled=True,
        )
        self.assertTrue(should)
        self.assertEqual(reason, REASON_DOC_INSUFFICIENT_POST_LLM)

    def test_passages_do_not_contain_the_asked_fact_is_a_gap(self):
        answer = (
            "The provided passages focus exclusively on early party organisation. "
            "The text does not contain any details regarding the 2018 amendment."
        )
        self.assertTrue(is_document_gap_answer(answer))
        should, reason = decide_web_after_answer(
            user_enabled=True,
            answer=answer,
            server_enabled=True,
        )
        self.assertTrue(should)
        self.assertEqual(reason, REASON_DOC_INSUFFICIENT_POST_LLM)

    def test_grounded_document_answer_does_not_search(self):
        answer = "Supervised learning uses labeled examples [E1]."
        self.assertFalse(is_document_gap_answer(answer))
        should, reason = decide_web_after_answer(
            user_enabled=True,
            answer=answer,
            server_enabled=True,
        )
        self.assertFalse(should)
        self.assertEqual(reason, REASON_DOC_SUFFICIENT)

    def test_quoted_couldnt_find_without_document_scope_does_not_search(self):
        answer = 'The paper notes that "researchers couldn\'t find a treatment in 1900." [E1]'
        self.assertFalse(is_document_gap_answer(answer))
        should, _reason = decide_web_after_answer(
            user_enabled=True,
            answer=answer,
            server_enabled=True,
        )
        self.assertFalse(should)

    def test_toggle_off_skips_gap(self):
        answer = "I couldn't find that in the provided document."
        should, reason = decide_web_after_answer(
            user_enabled=False,
            answer=answer,
            server_enabled=True,
        )
        self.assertFalse(should)
        self.assertEqual(reason, REASON_WEB_SKIPPED_TOGGLE_OFF)

    def test_off_topic_retrieval_triggers_web_without_refusal_phrasing(self):
        war = (
            "The retrieved pages describe naval campaigns, occupation policy, "
            "and the aftermath of a 20th century war in Europe."
        )
        self.assertTrue(passages_miss_question("who won the world cup in 2022", war))
        should, reason = decide_web_after_answer(
            user_enabled=True,
            answer="The files discuss occupation policy and campaigns.",
            question="who won the world cup in 2022",
            passages=war,
            server_enabled=True,
        )
        self.assertTrue(should)
        self.assertEqual(reason, REASON_DOC_OFF_TOPIC)

    def test_on_topic_passages_do_not_trigger_coverage_miss(self):
        football = (
            "Argentina won the 2022 FIFA World Cup in Qatar. "
            "Lionel Messi lifted the trophy after the final in Lusail."
        )
        self.assertFalse(
            passages_miss_question("who won the world cup in 2022", football)
        )
        should, reason = decide_web_after_answer(
            user_enabled=True,
            answer="Argentina won the 2022 World Cup [E1].",
            question="who won the world cup in 2022",
            passages=football,
            server_enabled=True,
        )
        self.assertFalse(should)
        self.assertEqual(reason, REASON_DOC_SUFFICIENT)

    def test_world_cup_style_refusal_is_a_gap(self):
        answer = (
            "I couldn't find that in the provided document. The retrieved passages "
            "focus entirely on the history, campaigns, and aftermath of a war, "
            "and they do not contain any information about sports or who won "
            "the 2022 World Cup."
        )
        self.assertTrue(is_document_gap_answer(answer))
        should, reason = decide_web_after_answer(
            user_enabled=True,
            answer=answer,
            server_enabled=True,
        )
        self.assertTrue(should)
        self.assertEqual(reason, REASON_DOC_INSUFFICIENT_POST_LLM)

    def test_extractive_excerpt_is_treated_as_a_gap(self):
        answer = (
            "The provided passages discuss this. Supporting excerpt:\n\n"
            "its ultimate expression in the form of progroms"
        )
        self.assertTrue(is_document_gap_answer(answer))
        should, reason = decide_web_after_answer(
            user_enabled=True,
            answer=answer,
            server_enabled=True,
        )
        self.assertTrue(should)
        self.assertEqual(reason, REASON_DOC_INSUFFICIENT_POST_LLM)

    def test_later_period_code_is_not_covered_by_earlier_pages(self):
        early = (
            "The files cover party organisation and agitation in 1919. "
            "They mention hostile newspaper articles from that year."
        )
        self.assertTrue(
            passages_miss_question(
                "what happened to the group in ww2",
                early,
            )
        )
        self.assertFalse(
            passages_miss_question(
                "what happened to the group in ww2",
                "The group faced occupation policy in 1942 and 1943.",
            )
        )

    def test_merge_keeps_pdf_and_web_cards(self):
        merged = merge_answer_sources(
            [{"kind": "pdf", "evidence_id": "E1", "chunk_id": "doc-a_0", "filename": "rules.pdf"}],
            [{"kind": "web", "evidence_id": "W1", "url": "https://www.theifab.com/laws"}],
        )
        kinds = [item["kind"] for item in merged]
        self.assertEqual(kinds, ["pdf", "web"])


class TestNoTopicHardcoding(unittest.TestCase):
    def test_web_fallback_package_has_no_topic_triggers(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent / "web_fallback"
        banned = ("hitler", "holocaust", "nazi")
        for path in root.rglob("*"):
            if path.suffix.lower() not in {".py", ".yaml", ".yml", ".json"}:
                continue
            text = path.read_text(encoding="utf-8").lower()
            for word in banned:
                self.assertNotIn(word, text, msg=f"{path} contains {word!r}")


class TestWebFallbackChatApi(unittest.TestCase):
    def setUp(self):
        self.conversation_id = "test-web-fallback"
        delete_conversation(self.conversation_id)
        self.client = api_client(app)
        self._live = patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["doc-a"],
        )
        self._live.start()

    def tearDown(self):
        self._live.stop()
        delete_conversation(self.conversation_id)

    def test_toggle_off_empty_retrieval_never_searches(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=_empty_retrieval(),
        ), patch(
            "web_fallback.orchestrator.search_web",
        ) as mock_search:
            response = self.client.post(
                "/chat",
                json={
                    "question": "What is the offside rule?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "web_fallback_enabled": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_search.assert_not_called()
        body = response.json()
        self.assertIn("no relevant information", body["answer"].lower())
        self.assertEqual(body["answer_origin"], "document")
        self.assertTrue(body["offer_web_fallback"])
        self.assertEqual(body["web_sources"], [])

    def test_toggle_on_empty_retrieval_uses_mock_web(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=_empty_retrieval(),
        ), patch(
            "web_fallback.orchestrator.search_web",
            wraps=None,
        ) as mock_search:
            mock_search.return_value = [
                WebHit(
                    title="Web lookup preview",
                    url="https://example.com/docusage-web-preview",
                    snippet="Development search result.",
                    domain="example.com",
                    preview=True,
                    provider="mock",
                )
            ]
            response = self.client.post(
                "/chat",
                json={
                    "question": "What is the offside rule?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "web_fallback_enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_search.assert_called_once()
        body = response.json()
        self.assertEqual(body["answer_origin"], "web_fallback")
        self.assertFalse(body["offer_web_fallback"])
        self.assertEqual(body["sources"], [])
        self.assertEqual(len(body["web_sources"]), 1)
        self.assertEqual(body["web_sources"][0]["url"], "https://example.com/docusage-web-preview")
        self.assertIn("preview", body["answer"].lower())
        detail = self.client.get(f"/conversations/{self.conversation_id}").json()
        citations = detail["messages"][-1]["citations"]
        self.assertEqual(citations[0]["kind"], "web")

    def test_toggle_on_with_document_hits_does_not_search(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=_hit_retrieval(),
        ), patch(
            "rag.generate_response",
            return_value="Supervised learning uses labeled examples.",
        ), patch(
            "web_fallback.orchestrator.search_web",
        ) as mock_search:
            response = self.client.post(
                "/chat",
                json={
                    "question": "What is supervised learning?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "web_fallback_enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_search.assert_not_called()
        body = response.json()
        self.assertEqual(body["answer_origin"], "document")
        self.assertIn("supervised", body["answer"].lower())
        self.assertEqual(body["web_sources"], [])

    def test_stream_toggle_on_empty_retrieval_emits_web_frame(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=_empty_retrieval(),
        ):
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": "What is the offside rule?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "web_fallback_enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertIn("__WEB_SOURCES__", text)
        self.assertIn("__END_WEB_SOURCES__", text)
        self.assertIn("preview", text.lower())
        self.assertNotIn("No relevant information found in the document.", text)

    def test_small_talk_with_toggle_on_does_not_search(self):
        with patch("web_fallback.orchestrator.search_web") as mock_search:
            response = self.client.post(
                "/chat",
                json={
                    "question": "hi",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "web_fallback_enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_search.assert_not_called()
        self.assertIn("hello", response.json()["answer"].lower())

    def test_stream_live_hits_uses_web_prompt_not_preview_copy(self):
        live = [
            WebHit(
                title="Laws of the Game",
                url="https://www.theifab.com/laws/offside",
                snippet="A player is in an offside position if nearer to the opponents' goal line.",
                domain="theifab.com",
                provider="tavily",
                preview=False,
                tier="t1",
            )
        ]
        with patch(
            "rag.retrieve_candidates",
            return_value=_empty_retrieval(),
        ), patch(
            "web_fallback.orchestrator.search_web",
            return_value=live,
        ), patch(
            "backend.generate_response_stream",
            return_value=iter(["A player is offside when nearer the goal line."]),
        ):
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": "What is the offside rule?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "web_fallback_enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertIn("__WEB_SOURCES__", text)
        self.assertIn("theifab.com", text)
        self.assertIn("nearer the goal line", text)
        self.assertNotIn("not a live trusted-site answer yet", text.lower())

    def test_post_llm_gap_keeps_document_answer_and_adds_web(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=_related_gap_retrieval(),
        ), patch(
            "rag.generate_response",
            side_effect=_generate_doc_or_web,
        ), patch(
            "llm_service.generate_response",
            side_effect=_generate_doc_or_web,
        ), patch(
            "web_fallback.orchestrator.search_web",
            return_value=_trusted_web_hits(),
        ) as mock_search:
            response = self.client.post(
                "/chat",
                json={
                    "question": "What changed in the 2018 amendment?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "web_fallback_enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_search.assert_called_once()
        body = response.json()
        self.assertIn(body["answer_origin"], {"web_fallback", "mixed"})
        self.assertIn("2018 revision", body["answer"])
        self.assertNotIn("couldn't find", body["answer"].lower())
        self.assertNotIn("don't cover this question", body["answer"].lower())
        self.assertEqual(len(body["web_sources"]), 1)
        self.assertIn("theifab.com", body["web_sources"][0]["url"])

    def test_stream_post_llm_gap_keeps_pdf_citations(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=_related_gap_retrieval(),
        ), patch(
            "web_fallback.orchestrator.search_web",
            return_value=_trusted_web_hits(),
        ) as mock_search, patch(
            "backend.generate_response_stream",
            return_value=iter([DOC_GAP_ANSWER]),
        ), patch(
            "backend.generate_response",
            side_effect=_generate_doc_or_web,
        ), patch(
            "llm_service.generate_response",
            side_effect=_generate_doc_or_web,
        ):
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": "What changed in the 2018 amendment?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "web_fallback_enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_search.assert_called_once()
        text = response.text
        self.assertIn("__WEB_SOURCES__", text)
        self.assertIn("2018 revision", text)
        self.assertIn("theifab.com", text)
        self.assertNotIn("don't cover this question", text.lower())

    def test_off_topic_chat_skips_document_llm(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=_off_topic_retrieval(),
        ), patch(
            "rag.generate_response",
        ) as doc_llm, patch(
            "llm_service.generate_response",
            return_value="Argentina won the 2022 World Cup in Qatar.",
        ), patch(
            "web_fallback.orchestrator.search_web",
            return_value=_trusted_web_hits(),
        ) as mock_search:
            response = self.client.post(
                "/chat",
                json={
                    "question": "who won the world cup in 2022",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "web_fallback_enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        doc_llm.assert_not_called()
        mock_search.assert_called_once()
        body = response.json()
        self.assertEqual(body["answer_origin"], "web_fallback")
        self.assertNotIn("don't cover this question", body["answer"].lower())
        self.assertNotIn("couldn't find", body["answer"].lower())
        self.assertIn("Argentina won the 2022 World Cup", body["answer"])
        self.assertEqual(body["sources"], [])
        self.assertEqual(len(body["web_sources"]), 1)

    def test_web_search_uses_rewritten_followup_query(self):
        prepared = {
            "answer": "",
            "sources": [{"filename": "ml.pdf"}],
            "prompt": "use E1",
            "recall_candidates": [
                {
                    "filename": "ml.pdf",
                    "text": "For example, predicting house prices from labeled sales data.",
                }
            ],
            "search_query": "bitcoin latest price",
            "question": "what is it latest price",
        }
        with patch(
            "backend.ask_question",
            return_value=prepared,
        ), patch(
            "web_fallback.orchestrator.search_web",
            return_value=_trusted_web_hits(),
        ) as mock_search, patch(
            "llm_service.generate_response",
            return_value="Bitcoin is a cryptocurrency.",
        ):
            response = self.client.post(
                "/chat",
                json={
                    "question": "what is it latest price",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "web_fallback_enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_search.assert_called_once()
        queried = mock_search.call_args[0][0].lower()
        self.assertIn("bitcoin", queried)
        self.assertNotIn("don't cover this question", response.json()["answer"].lower())

    def test_stream_off_topic_notes_then_web_without_document_generate(self):
        prompts: list[str] = []

        def stream_web(prompt: str):
            prompts.append(prompt)
            return iter(["Argentina won the 2022 World Cup in Qatar."])

        with patch(
            "rag.retrieve_candidates",
            return_value=_off_topic_retrieval(),
        ), patch(
            "web_fallback.orchestrator.search_web",
            return_value=_trusted_web_hits(),
        ) as mock_search, patch(
            "backend.generate_response_stream",
            side_effect=stream_web,
        ), patch(
            "rag.generate_response",
        ) as doc_llm:
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": "who won the world cup in 2022",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "web_fallback_enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        doc_llm.assert_not_called()
        mock_search.assert_called_once()
        self.assertEqual(len(prompts), 1)
        self.assertIn("Web passages:", prompts[0])
        self.assertIn("Lead with the fact", prompts[0])
        self.assertNotIn("provided document", prompts[0].lower())
        text = response.text
        self.assertNotIn("don't cover this question", text.lower())
        self.assertNotIn("no relevant information", text.lower())
        self.assertIn("Argentina won the 2022 World Cup", text)
        self.assertIn("__WEB_SOURCES__", text)
        self.assertIn("__STATUS__", text)
        self.assertIn("Searching the web", text)
        self.assertNotIn("1990s wording", text)


class TestLiveSearchProvider(unittest.TestCase):
    def test_tavily_parses_hits_and_drops_localhost(self):
        payload = {
            "results": [
                {
                    "title": "IFAB Laws",
                    "url": "https://www.theifab.com/laws",
                    "content": "A player is in an offside position if...",
                },
                {
                    "title": "Local junk",
                    "url": "http://localhost/admin",
                    "content": "should never be used",
                },
            ]
        }
        with patch("web_fallback.http.post_json", return_value=payload) as mocked:
            hits = TavilyWebSearchProvider("secret-key").search("offside")

        mocked.assert_called_once()
        self.assertEqual(len(hits), 1)
        self.assertFalse(hits[0].preview)
        self.assertEqual(hits[0].domain, "theifab.com")
        self.assertEqual(hits[0].provider, "tavily")
        self.assertNotIn("topic", mocked.call_args.kwargs.get("body") or {})

    def test_tavily_recency_uses_news_window_and_keeps_published_date(self):
        payload = {
            "results": [
                {
                    "title": "Match report",
                    "url": "https://www.espn.com/soccer/report/latest",
                    "content": "The last match finished 2-1.",
                    "published_date": "2026-09-21",
                },
            ]
        }
        with patch("web_fallback.http.post_json", return_value=payload) as mocked:
            hits = TavilyWebSearchProvider("secret-key").search(
                "last match", recency=True
            )

        body = mocked.call_args.kwargs.get("body") or {}
        self.assertEqual(body.get("topic"), "news")
        self.assertEqual(body.get("days"), 30)
        self.assertEqual(len(hits), 1)
        self.assertIn("2026-09-21", hits[0].snippet)

    def test_search_web_broadens_when_trusted_hits_are_thin(self):
        class FakeProvider:
            name = "tavily"

            def __init__(self):
                self.calls: list[list[str] | None] = []

            def search(self, query, *, include_domains=None, recency=False):
                self.calls.append(include_domains)
                wiki = WebHit(
                    title="Offside",
                    url="https://en.wikipedia.org/wiki/Offside_(association_football)",
                    snippet="Offside is a law in association football.",
                    domain="en.wikipedia.org",
                    provider="tavily",
                    preview=False,
                )
                blocked = WebHit(
                    title="Quora",
                    url="https://www.quora.com/offside",
                    snippet="I think offside is...",
                    domain="quora.com",
                    provider="tavily",
                    preview=False,
                )
                blog = WebHit(
                    title="Tactics blog",
                    url="https://random-tactics.example.net/offside",
                    snippet="Offside traps are a defensive tactic.",
                    domain="random-tactics.example.net",
                    provider="tavily",
                    preview=False,
                )
                if include_domains:
                    return [wiki, blocked]
                return [wiki, blocked, blog]

        fake = FakeProvider()
        with patch(
            "web_fallback.orchestrator.get_search_provider",
            return_value=fake,
        ), patch(
            "web_fallback.orchestrator._limits",
            return_value=(5, 2, False, 30),
        ):
            hits = search_web("offside")

        self.assertGreaterEqual(len(fake.calls), 1)
        self.assertTrue(all(call is None for call in fake.calls))
        urls = [hit.url for hit in hits]
        self.assertTrue(any("wikipedia.org" in url for url in urls))
        self.assertTrue(any("example.net" in url for url in urls))
        self.assertTrue(all("quora.com" not in url for url in urls))


if __name__ == "__main__":
    unittest.main()
