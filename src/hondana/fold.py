"""Text folding for matching Japanese / CJK book metadata.

``fold()`` produces a *matching key*, not display text: it is lossy on purpose.
Each step can be switched off when you need something gentler.
"""
from __future__ import annotations

import re
import unicodedata

from ._tables import EXTRA_FOLD, HAN_MAP, KYU_TO_SHIN, SIMP_TO_SHIN

__all__ = [
    "fold", "kata_to_hira", "hira_to_kata", "to_shinjitai", "width", "strip_reading_lines", "fold_small_kana",
    "fold_iteration_marks",
]

_HAN_TRANS = str.maketrans(HAN_MAP)
_KYU_TRANS = str.maketrans(KYU_TO_SHIN)
_SIMP_TRANS = str.maketrans(SIMP_TO_SHIN)
_EXTRA_TRANS = str.maketrans(EXTRA_FOLD)
_SMALL_KANA = str.maketrans(
    "ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶ",
    "あいうえおつやゆよわかけアイウエオツヤユヨワカケ",
)
_SPACE_RE = re.compile(r"[\s\u3000]+")
_PUNCT_RE = re.compile(r"[\s:：・･\-‐=＝,，、。.．!！?？'\"“”‘’()（）\[\]［］~]+")


# NFKC turns the spacing marks ゛ ゜ (U+309B/C) into a space + combining mark,
# which then never joins the kana before it: 「か゛」 would stay two characters.
_LOOSE_MARK_RE = re.compile(r"(?<=[ぁ-ヿ]) (?=[゙゚])")


def width(text: str) -> str:
    """Full-width ASCII → half-width, half-width katakana → full-width (NFKC).

    Voiced / semi-voiced marks are joined to the kana before them, whether they
    come as combining U+3099/U+309A or as the spacing 「゛」「゜」 some catalogues use:

    >>> width("カ゛") == width("ガ") == width("ｶﾞ") == "ガ"
    True

    A mark that has no precomposed form with its kana (「あ゛」) is kept as a
    combining mark.
    """
    s = unicodedata.normalize("NFKC", text)
    if "゙" in s or "゚" in s:
        s = unicodedata.normalize("NFC", _LOOSE_MARK_RE.sub("", s))
    return s


def kata_to_hira(text: str) -> str:
    """ァ-ヶ → ぁ-ゖ. Leaves ー and other marks alone."""
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in text)


def hira_to_kata(text: str) -> str:
    return "".join(chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c for c in text)


def fold_small_kana(text: str) -> str:
    """Small kana → full-size (ぁ→あ, っ→つ, ャ→ヤ, ヶ→ケ), for fuzzy matching
    when one source writes 「キャット」 and another 「キヤツト」 (old-style catalogues)."""
    return text.translate(_SMALL_KANA)


_KANA_MARKS = {"ゝ": False, "ゞ": True, "ヽ": False, "ヾ": True}


def _voicing(c: str, voiced: bool) -> str:
    """Return ``c`` with dakuten added (voiced) or removed (unvoiced), if possible."""
    base = unicodedata.normalize("NFD", c)[0]
    if not voiced:
        return base
    v = unicodedata.normalize("NFC", base + "\u3099")
    return v if len(v) == 1 else base


def fold_iteration_marks(text: str, mode: str = "expand") -> str:
    """Handle iteration marks 々 ゝ ゞ ヽ ヾ.

    ``mode="expand"`` repeats the previous character (「時々」→「時時」,
    「いすゞ」→「いすず」, 「こゝろ」→「こころ」); ``mode="drop"`` removes them.
    A mark with nothing before it is dropped in either mode.
    """
    if mode not in ("expand", "drop"):
        raise ValueError(f"mode must be 'expand' or 'drop', not {mode!r}")
    out: list[str] = []
    for c in text:
        if c == "々" or c in _KANA_MARKS:
            if mode == "expand" and out and not out[-1].isspace():
                prev = out[-1]
                out.append(prev if c == "々" else _voicing(prev, _KANA_MARKS[c]))
            continue
        out.append(c)
    return "".join(out)


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
    small_kana: bool = False,
    iteration_marks: str | None = None,
) -> str:
    """Return a key so that 「圖書館」「图书馆」「図書館」 compare equal, as do
    「ハリー・ポッター」「はりーぽったー」「ﾊﾘｰ ﾎﾟｯﾀｰ」 and 「ＡＢＣ」「abc」.

    >>> fold("ﾊﾘｰ・ﾎﾟｯﾀｰ") == fold("はりー ぽったー")
    True
    >>> fold("圖書館") == fold("图书馆") == fold("図書館")
    True

    ``small_kana=True`` additionally folds small kana to full size (off by
    default because it merges e.g. 「きって」 and 「きつて」):

    >>> fold("キャット", small_kana=True) == fold("キヤツト", small_kana=True)
    True

    ``iteration_marks="expand"`` or ``"drop"`` handles 々 ゝ ゞ (off by default):

    >>> fold("いすゞ", iteration_marks="expand") == fold("いすず")
    True
    """
    if not text:
        return ""
    s = width(text).translate(_EXTRA_TRANS)
    if iteration_marks is not None:
        s = fold_iteration_marks(s, iteration_marks)
    if han:
        s = to_shinjitai(s)
    if kana:
        s = kata_to_hira(s)
    if small_kana:
        s = fold_small_kana(s)
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
