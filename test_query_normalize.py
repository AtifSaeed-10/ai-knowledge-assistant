import unittest

from query_normalize import (
    build_vocabulary,
    correct_query,
    detect_small_talk,
    looks_misspelled,
    needs_correction,
    small_talk_answer,
)

ML_PASSAGES = [
    "Supervised learning uses labeled training examples to fit a model.",
    "In supervised learning the algorithm learns a mapping from inputs to outputs.",
    "Unsupervised learning finds structure in unlabeled data instead.",
    "Reinforcement learning optimises a policy through reward signals.",
    "Entropy measures the average amount of information in a random variable.",
]

HISTORY_PASSAGES = [
    "Hindenburg appointed Hitler chancellor in January 1933.",
    "The Reichstag fire decree suspended civil liberties across Germany.",
]


class TestSmallTalk(unittest.TestCase):
    def test_greetings_are_recognised(self):
        for text in ["hi", "Hello!", "hey there", "good morning", "Hii"]:
            self.assertEqual(detect_small_talk(text), "greeting", text)

    def test_thanks_and_goodbye(self):
        self.assertEqual(detect_small_talk("thanks!"), "thanks")
        self.assertEqual(detect_small_talk("thank you so much"), "thanks")
        self.assertEqual(detect_small_talk("bye"), "farewell")

    def test_real_questions_are_not_small_talk(self):
        for text in [
            "hi, what is supervised learning",
            "hello can you summarize this document",
            "what is a high five",
            "history of the treaty",
            "",
        ]:
            self.assertIsNone(detect_small_talk(text), text)

    def test_reply_mentions_documents(self):
        self.assertIn("PDFs", small_talk_answer("greeting"))


class TestMisspellingSignals(unittest.TestCase):
    def test_dropped_vowels_look_wrong(self):
        self.assertTrue(looks_misspelled("sprved"))
        self.assertTrue(looks_misspelled("lernng"))

    def test_ordinary_words_are_left_alone(self):
        for word in ["explain", "learning", "the", "document", "through", "nanjing"]:
            self.assertFalse(looks_misspelled(word), word)

    def test_gate_skips_clean_questions(self):
        self.assertFalse(needs_correction("what is supervised learning"))
        self.assertTrue(needs_correction("Explain sprved lernng"))


class TestCorrectQuery(unittest.TestCase):
    def test_typo_resolves_to_indexed_wording(self):
        vocabulary = build_vocabulary(ML_PASSAGES)
        corrected = correct_query("Explain sprved lernng", vocabulary)
        self.assertIn("supervised", corrected.lower())
        self.assertIn("learning", corrected.lower())

    def test_dropped_vowel_entropy_is_corrected(self):
        vocabulary = build_vocabulary(ML_PASSAGES)
        self.assertTrue(looks_misspelled("entrpy"))
        self.assertTrue(needs_correction("TELL ME ABOUT ENTRPY"))
        corrected = correct_query("TELL ME ABOUT ENTRPY", vocabulary)
        self.assertIn("entropy", corrected.lower())

    def test_correction_only_uses_words_from_the_documents(self):
        # A history corpus has no machine-learning vocabulary, so the typed
        # words survive and retrieval refuses as usual.
        vocabulary = build_vocabulary(HISTORY_PASSAGES)
        self.assertEqual(
            correct_query("Explain sprved lernng", vocabulary),
            "Explain sprved lernng",
        )

    def test_clean_question_is_untouched(self):
        vocabulary = build_vocabulary(ML_PASSAGES)
        question = "What is supervised learning?"
        self.assertEqual(correct_query(question, vocabulary), question)

    def test_no_vocabulary_is_a_no_op(self):
        self.assertEqual(correct_query("Explain sprved lernng", {}), "Explain sprved lernng")

    def test_whole_sentence_garbage_is_not_rewritten(self):
        vocabulary = build_vocabulary(ML_PASSAGES)
        noise = "sprved lernng unsprvsd lrnng rnfrcmnt"
        self.assertEqual(correct_query(noise, vocabulary), noise)


if __name__ == "__main__":
    unittest.main()
