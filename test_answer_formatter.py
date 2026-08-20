"""Tests for answer post-processing."""

from __future__ import annotations

import unittest

from answer_formatter import (
    polish_answer_text,
    remove_prose_quote_dumps,
    truncate_marker_quotes,
)


class TestRemoveProseQuoteDumps(unittest.TestCase):
    def test_strips_long_inline_quote_but_keeps_marker(self):
        text = (
            'Supervised learning uses labels. '
            '"A supervised learning is so called because the process of an algorithm '
            'learning from the training dataset can be thought of as a teacher supervising '
            'the learning process." '
            'It includes classification.[E1:"labeled training set"]'
        )
        cleaned = remove_prose_quote_dumps(text)
        self.assertNotIn("teacher supervising", cleaned)
        self.assertIn('[E1:"labeled training set"]', cleaned)
        self.assertIn("Supervised learning uses labels", cleaned)

    def test_keeps_short_inline_quotes(self):
        text = 'It is called "supervised learning" because labels are known.[E1:"supervised learning"]'
        self.assertEqual(remove_prose_quote_dumps(text), text)


class TestTruncateMarkerQuotes(unittest.TestCase):
    def test_shortens_long_marker_quote(self):
        long_quote = "word " * 40
        text = f'Claim.[E1:"{long_quote.strip()}"]'
        cleaned = truncate_marker_quotes(text)
        self.assertIn("[E1:", cleaned)
        self.assertNotIn(long_quote.strip(), cleaned)
        self.assertLess(len(cleaned), len(text))


class TestPolishAnswerText(unittest.TestCase):
    def test_combined_cleanup(self):
        text = (
            "Definition here.\n\n\n"
            '"This is a very long quoted passage that should not appear in the final '
            'answer because it duplicates what was already paraphrased above." '
            'More detail.[E2:"short supporting quote"]'
        )
        polished = polish_answer_text(text)
        self.assertNotIn("very long quoted passage", polished)
        self.assertIn('[E2:"short supporting quote"]', polished)


if __name__ == "__main__":
    unittest.main()
