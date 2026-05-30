"""Arabic + mixed-script normalisation for search-term intelligence.

GCC search-terms reports are messy: diacritics, alef variants, tatweel
(kashida), Arabic-Indic and Eastern Arabic-Indic digits, and English mixed in.
Normalising before n-gram and intent work materially improves matching. None of
this changes display strings, it only produces a canonical comparison key.
"""
from __future__ import annotations

import re
import unicodedata

# Arabic diacritics (harakat) and the tatweel elongation character.
_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED\u0640]")

# Digit folding: Arabic-Indic (\u0660-\u0669) and Eastern Arabic-Indic
# (\u06F0-\u06F9) mapped to ASCII so "اشتري ٣ ابواب" matches "buy 3 doors".
_DIGIT_MAP = {**{chr(0x0660 + i): str(i) for i in range(10)},
              **{chr(0x06F0 + i): str(i) for i in range(10)}}

# Letter folding: unify alef hamza forms, taa marbuta -> haa, alef maqsura -> yaa.
_LETTER_MAP = {
    "\u0622": "\u0627", "\u0623": "\u0627", "\u0625": "\u0627",  # آ أ إ -> ا
    "\u0629": "\u0647",  # ة -> ه
    "\u0649": "\u064A",  # ى -> ي
    "\u0624": "\u0648",  # ؤ -> و
    "\u0626": "\u064A",  # ئ -> ي
}

_ARABIC_RANGE = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")


def contains_arabic(text: str) -> bool:
    return bool(_ARABIC_RANGE.search(text or ""))


def normalise(text: str) -> str:
    """Canonical comparison key. Lowercases Latin, folds Arabic letters/digits,
    strips diacritics and tatweel, collapses whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = "".join(_DIGIT_MAP.get(ch, ch) for ch in text)
    text = _DIACRITICS.sub("", text)
    text = "".join(_LETTER_MAP.get(ch, ch) for ch in text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokens(text: str) -> list[str]:
    """Whitespace + punctuation tokeniser that keeps Arabic and Latin word
    characters and ASCII digits, dropping everything else."""
    norm = normalise(text)
    return re.findall(r"[a-z0-9]+|[\u0600-\u06FF\u0750-\u077F]+", norm)
