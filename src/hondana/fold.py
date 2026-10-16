"""Text folding for matching Japanese / CJK book metadata.

``fold()`` produces a *matching key*, not display text: it is lossy on purpose.
Each step can be switched off when you need something gentler.
"""
from __future__ import annotations

import re
import unicodedata

from ._tables import EXTRA_FOLD, HAN_MAP, KYU_TO_SHIN, SIMP_TO_SHIN

__all__ = ["fold", "kata_to_hira", "hira_to_kata", "to_shinjitai", "width", "strip_reading_lines"]

_HAN_TRANS = str.maketrans(HAN_MAP)
_KYU_TRANS = str.maketrans(KYU_TO_SHIN)
_SIMP_TRANS = str.maketrans(SIMP_TO_SHIN)
_EXTRA_TRANS = str.maketrans(EXTRA_FOLD)
_SPACE_RE = re.compile(r"[\s\u3000]+")
_PUNCT_RE = re.compile(r"[\s:：・･\-‐=＝,，、。.．!！?？'\"“”‘’()（）\[\]［］~]+")


def width(text: str) -> str:
    """Full-width ASCII → half-width, half-width katakana → full-width (NFKC)."""
    return unicodedata.normalize("NFKC", text)


def kata_to_hira(text: str) -> str:
    """ァ-ヶ → ぁ-ゖ. Leaves ー and other marks alone."""
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in text)


def hira_to_kata(text: str) -> str:
    return "".join(chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c for c in text)


def to_shinjitai(text: str, *, simplified: bool = True, kyujitai: bool = True) -> str:
    """Map kyujitai / traditional and (optionally) simplified Chinese to shinjitai."""
    if simplified and kyujitai:
        return text.translate(_HAN_TRANS)
    if kyujitai:
        return text.translate(_KYU_TRANS)
    if simplified:
        return text.translate(_SIMP_TRANS)
    return text


def fold(
    text: str | None,
    *,
    kana: bool = True,
    han: bool = True,
    long_vowel: bool = True,
    punctuation: bool = True,
    lower: bool = True,
) -> str:
    """Return a key so that 「圖書館」「图书馆」「図書館」 compare equal, as do
    「ハリー・ポッター」「はりーぽったー」「ﾊﾘｰ ﾎﾟｯﾀｰ」 and 「ＡＢＣ」「abc」.

    >>> fold("ﾊﾘｰ・ﾎﾟｯﾀｰ") == fold("はりー ぽったー")
    True
    >>> fold("圖書館") == fold("图书馆") == fold("図書館")
    True
    """
    if not text:
        return ""
    s = width(text).translate(_EXTRA_TRANS)
    if han:
        s = to_shinjitai(s)
    if kana:
        s = kata_to_hira(s)
    if lower:
        s = s.casefold()
    if long_vowel:
        s = s.replace("ー", "")
    s = _PUNCT_RE.sub("", s) if punctuation else _SPACE_RE.sub(" ", s).strip()
    return s


_HAS_KANJI_OR_HIRA = re.compile(r"[\u3040-\u309f\u4e00-\u9fff]")


def strip_reading_lines(value: str) -> str:
    """Catalogues often append a katakana reading on its own line
    (``"吾輩は猫である\\nワガハイ ワ ネコ デ アル"``). Keep the first line and any
    later line that contains kanji or hiragana."""
    lines = value.split("\n")
    return "\n".join(l for i, l in enumerate(lines) if i == 0 or _HAS_KANJI_OR_HIRA.search(l))
