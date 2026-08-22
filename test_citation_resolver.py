"""Unit tests for claim-linked citation IDs and stream holdback."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import app
from citation_resolver import (
    CitationStreamResolver,
    attach_quotes_to_sources,
    display_number,
    evidence_id_for_index,
    iter_resolved_stream,
    quotes_by_evidence_id,
    resolve_answer,
    resolve_evidence_markers,
    sanitize_quote,
    split_unclosed_bracket,
)
from memory.store import delete_conversation, get_conversation, load_conversation
from rag import _dedupe_sources, ask_question


class TestEvidenceIdHelpers(unittest.TestCase):
    def test_stable_ids_and_display_numbers(self):
        self.assertEqual(evidence_id_for_index(1), "E1")
        self.assertEqual(evidence_id_for_index(12), "E12")
        self.assertEqual(display_number("E1"), 1)
        self.assertEqual(display_number("E12"), 12)
        self.assertIsNone(display_number("E0"))
        self.assertIsNone(display_number("nope"))


class TestResolveMarkers(unittest.TestCase):
    def setUp(self):
        self.valid = {"E1", "E2"}

    def test_valid_id_is_preserved(self):
        text = "Supervised learning uses labeled examples.[E1]"
        self.assertEqual(resolve_evidence_markers(text, self.valid), text)

    def test_invalid_id_is_removed(self):
        text = "A claim.[E9] Still true."
        self.assertEqual(
            resolve_evidence_markers(text, self.valid),
            "A claim. Still true.",
        )

    def test_mixed_valid_and_invalid(self):
        text = "A.[E1] B.[E9] C.[E2]"
        self.assertEqual(
            resolve_evidence_markers(text, self.valid),
            "A.[E1] B. C.[E2]",
        )

    def test_duplicate_adjacent_markers_collapse(self):
        text = "A claim.[E1][E1]"
        self.assertEqual(resolve_evidence_markers(text, self.valid), "A claim.[E1]")

    def test_multiple_distinct_citations(self):
        text = "Classification and regression.[E1][E2]"
        self.assertEqual(resolve_evidence_markers(text, self.valid), text)

    def test_comma_group_keeps_valid_order_and_dedupes(self):
        text = "Both apply.[E2, E1, E9, E2]"
        self.assertEqual(
            resolve_evidence_markers(text, self.valid),
            "Both apply.[E2][E1]",
        )

    def test_markdown_brackets_are_left_alone(self):
        text = "See [the paper](https://example.com) for more."
        self.assertEqual(resolve_evidence_markers(text, self.valid), text)

    def test_empty_valid_set_strips_all_e_ids(self):
        text = "A claim.[E1]"
        self.assertEqual(resolve_evidence_markers(text, set()), "A claim.")

    def test_resolve_answer_uses_source_ids(self):
        sources = [{"evidence_id": "E1", "chunk_id": "c1"}]
        self.assertEqual(
            resolve_answer("Fact.[E1] Nope.[E3]", sources),
            "Fact.[E1] Nope.",
        )


class TestStreamHoldback(unittest.TestCase):
    def test_partial_markers_are_held(self):
        self.assertEqual(split_unclosed_bracket("Hello ["), ("Hello ", "["))
        self.assertEqual(split_unclosed_bracket("Hello [E"), ("Hello ", "[E"))
        self.assertEqual(split_unclosed_bracket("Hello [E1"), ("Hello ", "[E1"))
        self.assertEqual(split_unclosed_bracket("Hello [E1]"), ("Hello [E1]", ""))

    def test_stream_does_not_emit_broken_markers(self):
        sources = [{"evidence_id": "E1"}]
        resolver = CitationStreamResolver(sources)
        emitted = []
        emitted.append(resolver.feed("Hello ["))
        emitted.append(resolver.feed("E"))
        emitted.append(resolver.feed("1"))
        self.assertEqual("".join(emitted), "Hello ")
        self.assertNotIn("[", "".join(emitted))
        emitted.append(resolver.feed("] world.[E9]"))
        emitted.append(resolver.close())
        self.assertEqual("".join(emitted), "Hello [E1] world.")
        self.assertNotIn("[E9]", "".join(emitted))

    def test_stream_drops_incomplete_marker_at_end(self):
        sources = [{"evidence_id": "E1"}]
        emitted = "".join(iter_resolved_stream(["Fact.", "[E"], sources))
        self.assertEqual(emitted, "Fact.")
        self.assertNotIn("[E", emitted)

    def test_stable_numbering_does_not_reorder_by_appearance(self):
        sources = [{"evidence_id": "E1"}, {"evidence_id": "E2"}]
        text = "Second first.[E2] Then first.[E1]"
        self.assertEqual(resolve_evidence_markers(text, {"E1", "E2"}), text)
        self.assertEqual(display_number("E2"), 2)


class TestQuotedMarkers(unittest.TestCase):
    def setUp(self):
        self.valid = {"E1", "E2"}

    def test_valid_quote_is_preserved(self):
        text = 'A claim.[E1:"supervised learning uses labeled examples"]'
        self.assertEqual(resolve_evidence_markers(text, self.valid), text)

    def test_pipe_quote_form_is_normalized(self):
        text = 'A claim.[E1|quote="supervised learning uses labeled examples"]'
        self.assertEqual(
            resolve_evidence_markers(text, self.valid),
            'A claim.[E1:"supervised learning uses labeled examples"]',
        )

    def test_invalid_eid_with_quote_is_removed(self):
        text = 'A claim.[E9:"supervised learning uses labeled examples"] Still true.'
        self.assertEqual(
            resolve_evidence_markers(text, self.valid),
            "A claim. Still true.",
        )

    def test_bad_quote_keeps_valid_eid(self):
        text = 'A claim.[E1:"x0=12 y0=40 bbox"]'
        self.assertEqual(resolve_evidence_markers(text, self.valid), "A claim.[E1]")

    def test_fake_coordinates_are_stripped_from_marker(self):
        text = "A claim.[E1|x0=12.5|y0=40|coord_space=pdf]"
        self.assertEqual(resolve_evidence_markers(text, self.valid), "A claim.[E1]")
        self.assertIsNone(sanitize_quote("x0=12 y0=40 x1=80 y1=56"))

    def test_unknown_eid_coordinates_are_dropped(self):
        text = "A claim.[E9|x0=1|y0=2] Done."
        self.assertEqual(resolve_evidence_markers(text, self.valid), "A claim. Done.")

    def test_same_eid_different_quotes_are_kept(self):
        text = (
            'First.[E1:"supervised learning uses labeled examples"] '
            'Second.[E1:"classification and regression tasks"]'
        )
        self.assertEqual(resolve_evidence_markers(text, self.valid), text)

    def test_identical_quoted_markers_collapse(self):
        text = (
            'A claim.[E1:"supervised learning uses labeled examples"]'
            '[E1:"supervised learning uses labeled examples"]'
        )
        self.assertEqual(
            resolve_evidence_markers(text, self.valid),
            'A claim.[E1:"supervised learning uses labeled examples"]',
        )

    def test_plain_marker_without_quote_is_unchanged(self):
        text = "A claim.[E1]"
        self.assertEqual(resolve_evidence_markers(text, self.valid), text)

    def test_stream_holds_partial_quoted_marker(self):
        sources = [{"evidence_id": "E1"}]
        resolver = CitationStreamResolver(sources)
        emitted = []
        emitted.append(resolver.feed("Hello ["))
        emitted.append(resolver.feed('E1:"labeled'))
        self.assertEqual("".join(emitted), "Hello ")
        emitted.append(resolver.feed(' examples here"] world'))
        emitted.append(resolver.close())
        self.assertEqual(
            "".join(emitted),
            'Hello [E1:"labeled examples here"] world',
        )


class TestAttachQuotesToSources(unittest.TestCase):
    def test_only_used_ids_receive_quotes(self):
        sources = [
            {"evidence_id": "E1", "chunk_id": "c1"},
            {"evidence_id": "E2", "chunk_id": "c2"},
            {"evidence_id": "E3", "chunk_id": "c3"},
        ]
        answer = (
            'Supervised learning uses labeled examples.'
            '[E1:"supervised learning uses labeled examples"]'
        )
        attached = attach_quotes_to_sources(sources, answer)
        self.assertEqual(
            quotes_by_evidence_id(answer),
            {"E1": ["supervised learning uses labeled examples"]},
        )
        self.assertEqual(attached[0]["quote"], "supervised learning uses labeled examples")
        self.assertIsNone(attached[1]["quote"])
        self.assertIsNone(attached[2]["quote"])
        self.assertEqual([item["evidence_id"] for item in attached], ["E1", "E2", "E3"])

    def test_multiple_cited_quotes_are_kept_per_id(self):
        sources = [{"evidence_id": "E1"}, {"evidence_id": "E2"}]
        answer = (
            'A.[E1:"supervised learning uses labeled examples"] '
            'B.[E2:"classification and regression"]'
        )
        attached = attach_quotes_to_sources(sources, answer)
        self.assertEqual(attached[0]["quote"], "supervised learning uses labeled examples")
        self.assertEqual(attached[1]["quote"], "classification and regression")


class TestSourceDedupe(unittest.TestCase):
    def test_same_page_distinct_chunks_are_kept(self):
        sources = _dedupe_sources(
            [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page": 10,
                    "chunk_id": "doc-a_1",
                    "relevance": 90,
                    "evidence_id": "E1",
                },
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page": 10,
                    "chunk_id": "doc-a_2",
                    "relevance": 80,
                    "evidence_id": "E2",
                },
            ]
        )
        self.assertEqual([item["evidence_id"] for item in sources], ["E1", "E2"])

    def test_duplicate_chunk_id_is_collapsed(self):
        sources = _dedupe_sources(
            [
                {"chunk_id": "doc-a_1", "page": 10, "evidence_id": "E1"},
                {"chunk_id": "doc-a_1", "page": 10, "evidence_id": "E2"},
            ]
        )
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["evidence_id"], "E1")


class TestAskQuestionEvidenceIds(unittest.TestCase):
    def setUp(self):
        self._live = patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["doc-a"],
        )
        self._live.start()

    def tearDown(self):
        self._live.stop()

    def _retrieval_two_same_page(self):
        return {
            "chunks": ["Labeled examples.", "Classification and regression."],
            "distances": [0.1, 0.2],
            "metadata": [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": 42,
                },
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": 42,
                },
            ],
            "ids": ["doc-a_1", "doc-a_2"],
            "relevances": [90, 80],
            "reranker_scores": [2.0, 1.5],
            "rerank_fallback": False,
        }

    def test_assigns_stable_ids_and_labels_prompt(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval_two_same_page(),
        ), patch(
            "rag.generate_response",
            return_value="Supervised learning uses labeled examples.[E1] It supports classification.[E2] Fake.[E9]",
        ), patch(
            "claim_validator.enrich_source_with_quote_evidence",
            side_effect=lambda source, **kwargs: {
                **source,
                "quote": kwargs.get("quote"),
                "quotes": [kwargs.get("quote")] if kwargs.get("quote") else [],
                "quote_mapping_status": "none",
                "quote_highlight_available": False,
                "quote_regions": [],
            },
        ):
            result = ask_question("What is supervised learning?", None, ["doc-a"])

        ids = [item["evidence_id"] for item in result["sources"]]
        self.assertEqual(ids, ["E1", "E2"])
        self.assertEqual(result["sources"][0]["chunk_id"], "doc-a_1")
        self.assertEqual(result["sources"][1]["chunk_id"], "doc-a_2")
        self.assertEqual(result["sources"][0]["snippet"], "Labeled examples.")
        self.assertIsNone(result["sources"][0]["quote"])
        self.assertIsNone(result["sources"][1]["quote"])
        self.assertIn("[E1] ml.pdf, p. 42", result["prompt"])
        self.assertIn("[E2] ml.pdf, p. 42", result["prompt"])
        self.assertIn("Never invent ids", result["prompt"])
        self.assertIn("verbatim anchor", result["prompt"])
        self.assertIn("coordinates", result["prompt"])
        self.assertEqual(
            result["answer"],
            "Supervised learning uses labeled examples.[E1] It supports classification.[E2] Fake.",
        )

    def test_quoted_answer_keeps_quote_on_valid_id(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval_two_same_page(),
        ), patch(
            "rag.generate_response",
            return_value=(
                'Uses labels.[E1:"Labeled examples."] Also tasks.'
                '[E2:"Classification and regression."] Fake.[E9:"not real"]'
            ),
        ), patch(
            "claim_validator._chunk_text_for_source",
            side_effect=lambda source: {
                "doc-a_1": "Labeled examples.",
                "doc-a_2": "Classification and regression.",
            }.get(str(source.get("chunk_id")), ""),
        ), patch(
            "claim_validator.enrich_source_with_quote_evidence",
            side_effect=lambda source, **kwargs: {
                **source,
                "quote": kwargs.get("quote"),
                "quotes": [kwargs.get("quote")] if kwargs.get("quote") else [],
                "quote_mapping_status": "exact" if kwargs.get("quote") else "none",
                "quote_highlight_available": bool(kwargs.get("quote")),
                "quote_regions": [],
            },
        ):
            result = ask_question("What is supervised learning?", None, ["doc-a"])

        self.assertEqual(
            result["answer"],
            'Uses labels.[E1:"Labeled examples."] Also tasks.'
            '[E2:"Classification and regression."] Fake.',
        )
        self.assertEqual(result["sources"][0]["quote"], "Labeled examples.")
        self.assertEqual(result["sources"][1]["quote"], "Classification and regression.")


class TestStreamProtocolWithCitations(unittest.TestCase):
    def setUp(self):
        self.conversation_id = "test-stream-evidence-ids"
        delete_conversation(self.conversation_id)
        self.client = TestClient(app)
        self._live = patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["doc-a"],
        )
        self._live.start()

    def tearDown(self):
        self._live.stop()
        delete_conversation(self.conversation_id)

    def test_citations_envelope_includes_evidence_id_and_answer_is_resolved(self):
        retrieval = {
            "chunks": ["Supervised learning uses labeled data."],
            "distances": [0.25],
            "metadata": [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": 10,
                }
            ],
            "ids": ["doc-a_1"],
            "relevances": [90],
            "reranker_scores": [2.0],
            "rerank_fallback": False,
        }
        with patch(
            "rag.retrieve_candidates",
            return_value=retrieval,
        ), patch(
            "backend.generate_response_stream",
            return_value=iter(["Uses labels.", "[E1]", " Bad.", "[E4]"]),
        ):
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": "What is supervised learning?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertTrue(body.startswith("__CITATIONS__"))
        payload = body.split("__CITATIONS__", 1)[1].split("__END_CITATIONS__", 1)
        sources = json.loads(payload[0])
        self.assertEqual(sources[0]["evidence_id"], "E1")
        self.assertEqual(sources[0]["chunk_id"], "doc-a_1")
        answer = payload[1]
        self.assertIn("[E1]", answer)
        self.assertNotIn("[E4]", answer)

        history = load_conversation(self.conversation_id)
        self.assertEqual(history[1]["role"], "assistant")
        self.assertIn("[E1]", history[1]["content"])
        self.assertNotIn("[E4]", history[1]["content"])
        stored = get_conversation(self.conversation_id)
        assert stored is not None
        self.assertEqual(stored["messages"][1]["citations"][0]["evidence_id"], "E1")
        self.assertEqual(stored["messages"][1]["citations"][0]["snippet"], "Supervised learning uses labeled data.")
        self.assertIsNone(stored["messages"][1]["citations"][0]["quote"])

    def test_quoted_markers_survive_stream_and_attach_to_saved_citations(self):
        retrieval = {
            "chunks": [
                "Supervised learning uses labeled examples.",
                "Classification and regression tasks.",
            ],
            "distances": [0.1, 0.2],
            "metadata": [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": 10,
                },
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": 11,
                },
            ],
            "ids": ["doc-a_1", "doc-a_2"],
            "relevances": [100, 100],
            "reranker_scores": [2.0, 1.5],
            "rerank_fallback": False,
        }
        with patch(
            "rag.retrieve_candidates",
            return_value=retrieval,
        ), patch(
            "backend.generate_response_stream",
            return_value=iter(
                [
                    "Uses labels.",
                    '[E1:"labeled examples"]',
                    " Other retrieved sources stay uncited.",
                ]
            ),
        ), patch(
            "claim_validator._chunk_text_for_source",
            return_value="Supervised learning uses labeled examples.",
        ), patch(
            "claim_validator.enrich_source_with_quote_evidence",
            side_effect=lambda source, **kwargs: {
                **source,
                "quote": kwargs.get("quote"),
                "quotes": [kwargs.get("quote")] if kwargs.get("quote") else [],
                "quote_mapping_status": "exact",
                "quote_highlight_available": True,
                "quote_regions": [],
            },
        ):
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": "What is supervised learning?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.text
        payload = body.split("__CITATIONS__", 1)[1].split("__END_CITATIONS__", 1)
        sources = json.loads(payload[0])
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["evidence_id"], "E1")
        self.assertEqual(sources[1]["evidence_id"], "E2")
        self.assertIsNone(sources[0].get("quote"))
        self.assertEqual(sources[0]["snippet"], "Supervised learning uses labeled examples.")
        answer = payload[1]
        if "__CITATIONS_FINAL__" in answer:
            answer = answer.split("__CITATIONS_FINAL__", 1)[0]
        self.assertIn('[E1:"labeled examples"]', answer)
        self.assertNotIn("[E2]", answer)

        stored = get_conversation(self.conversation_id)
        assert stored is not None
        saved = stored["messages"][1]["citations"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["quote"], "labeled examples")
        self.assertEqual(saved[0]["evidence_id"], "E1")
        self.assertIn("__CITATIONS_FINAL__", body)


if __name__ == "__main__":
    unittest.main()
