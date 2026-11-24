"""Rule-based normalization used to ignore purely cosmetic differences.

Two paragraphs whose normalized text is identical are treated as unchanged:
punctuation, quote styles, dashes, Hebrew vowel marks (niqqud), direction
marks and extra whitespace do not count as a change.

Wording changes such as "אודות" -> "על אודות" are NOT caught here on purpose:
deciding whether a wording change matters is the job of the AI layer.
"""
import re
import unicodedata

_DIRECTION_MARKS = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮﻿"))
_PUNCT = re.compile(r"[\"'`׳״“”„‘’\-–—־.,;:!?()\[\]{}/\\]")
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))  # drop niqqud
    text = text.translate(_DIRECTION_MARKS)
    text = _PUNCT.sub(" ", text)
    return _SPACES.sub(" ", text).strip()
