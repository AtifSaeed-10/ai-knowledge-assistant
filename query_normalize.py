"""
Typo tolerance for the search query, and a local answer for small talk.

DocuSage stays a document assistant. Correcting "sprved lernng" to
"supervised learning" only changes what we search for; whether the answer
exists is still decided by the passages, and a topic the PDFs never cover
still gets the usual grounded refusal.

Corrections come from the indexed vocabulary, never from a general
dictionary, so a misspelling can only ever resolve to words the reader's
own documents actually contain.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
_VOWEL_RE = re.compile(r"[aeiou]", re.I)

# Short function words are never "misspelled" — they are just short.
_SKIP_TOKENS = frozenset(
    """
    a an the and or but if is are was were be been being am do does did
    of to for from in on at by with as it its this that these those
    what which who whom whose when where why how can could should would
    will not no yes so then than too very my your our their his her
    me you we they he she him them us i pdf doc file page pages
    """.split()
)

_GREETING_RE = re.compile(
    r"^(?:hi+|hey+|hello+|yo|hii+|helo+|hallo|salam|as-?salam(?:u|o)?\s*alaikum|"
    r"assalamualaikum|namaste|good\s+(?:morning|afternoon|evening|day))"
    r"(?:\s+(?:there|docusage|bro|dude|friend))?[\s!.,?]*$",
    re.I,
)
_THANKS_RE = re.compile(
    r"^(?:thanks?|thank\s*(?:you|u)|thx|tysm|ty|shukriya|appreciate\s+it|"
    r"got\s+it|nice|great|perfect|awesome|cool)"
    r"(?:\s+(?:a\s+lot|so\s+much|man|bro|docusage))?[\s!.,?]*$",
    re.I,
)
_FAREWELL_RE = re.compile(
    r"^(?:bye+|goodbye|good\s*night|see\s*(?:you|ya)(?:\s+later)?|take\s+care|"
    r"khuda\s*hafiz|allah\s*hafiz)[\s!.,?]*$",
    re.I,
)

SMALL_TALK_REPLIES = {
    "greeting": (
        "Hello. Ask me anything about your PDFs and I will answer with the "
        "page it came from."
    ),
    "thanks": "Happy to help. Ask me anything else from your PDFs.",
    "farewell": "Bye — your chats and documents will be here when you come back.",
}

_MAX_SMALL_TALK_CHARS = 40


def detect_small_talk(question: str) -> str | None:
    """Greeting / thanks / goodbye that no retrieval can answer."""
    text = (question or "").strip()
    if not text or len(text) > _MAX_SMALL_TALK_CHARS:
        return None
    if _GREETING_RE.match(text):
        return "greeting"
    if _THANKS_RE.match(text):
        return "thanks"
    if _FAREWELL_RE.match(text):
        return "farewell"
    return None


def small_talk_answer(kind: str) -> str:
    return SMALL_TALK_REPLIES.get(kind, SMALL_TALK_REPLIES["greeting"])


def looks_misspelled(token: str) -> bool:
    """
    Cheap signals for a garbled word: dropped vowels ("lernng"), a long
    run of consonants, or a doubled-up keyboard slip.
    """
    word = token.lower()
    if len(word) < 4 or word in _SKIP_TOKENS:
        return False
    if not _VOWEL_RE.search(word):
        return True

    vowels = len(_VOWEL_RE.findall(word))
    if len(word) >= 6 and vowels / len(word) < 0.28:
        return True
    if re.search(r"[bcdfghjklmnpqrstvwxz]{4,}", word):
        return True
    return False


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _best_match(token: str, vocabulary: dict[str, int]) -> str | None:
    """
    Closest indexed word, preferring ones that keep the typed letters in
    order — "sprved" is a subsequence of "supervised".
    """
    word = token.lower()
    best: tuple[float, int, str] | None = None

    for candidate, frequency in vocabulary.items():
        if abs(len(candidate) - len(word)) > max(4, len(word) // 2):
            continue
        if candidate[0] != word[0]:
            continue

        score = _similarity(word, candidate)
        if _is_subsequence(word, candidate):
            score += 0.15
        if score < 0.68:
            continue

        ranked = (round(score, 3), frequency, candidate)
        if best is None or ranked > best:
            best = ranked

    return best[2] if best else None


def _is_subsequence(short: str, long: str) -> bool:
    iterator = iter(long)
    return all(character in iterator for character in short)


def build_vocabulary(texts: list[str], limit: int = 20000) -> dict[str, int]:
    """Word counts from indexed passages — the only correction dictionary."""
    counts: dict[str, int] = {}
    for text in texts or []:
        if not isinstance(text, str):
            continue
        for match in _TOKEN_RE.findall(text):
            word = match.lower()
            if len(word) < 4 or word in _SKIP_TOKENS:
                continue
            counts[word] = counts.get(word, 0) + 1
            if len(counts) >= limit:
                break
    return counts


def needs_correction(question: str) -> bool:
    """Cheap gate so a clean question never pays for a vocabulary build."""
    return any(looks_misspelled(token) for token in _TOKEN_RE.findall(question or ""))


# A sentence where everything looks garbled is more likely a language we do
# not handle than a typo, so never rewrite it wholesale.
_MAX_CORRECTIONS = 3


def correct_query(question: str, vocabulary: dict[str, int]) -> str:
    """
    Rewrite only the tokens that look garbled and have a close match in the
    documents. Everything else is left exactly as the reader typed it.
    """
    text = question or ""
    if not text.strip() or not vocabulary:
        return text

    replacements: list[tuple[int, int, str]] = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0)
        if token.lower() in vocabulary:
            continue
        if not looks_misspelled(token):
            continue
        fixed = _best_match(token, vocabulary)
        if not fixed or fixed == token.lower():
            continue
        replacements.append((match.start(), match.end(), fixed))

    if not replacements or len(replacements) > _MAX_CORRECTIONS:
        return text

    out = []
    cursor = 0
    for start, end, fixed in replacements:
        out.append(text[cursor:start])
        out.append(fixed)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)
