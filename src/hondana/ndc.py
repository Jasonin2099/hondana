"""Label an NDC class mark with its main class (第1次区分 / 類目) only.

The Nippon Decimal Classification (日本十進分類法, NDC) is maintained by the
Japan Library Association (日本図書館協会), and its schedules are copyrighted.
hondana therefore ships only the ten one-digit main classes, as the JLA
explains them in public (https://www.jla.or.jp/ndc/, "第1次区分表（類目表）",
NDC 新訂10版): 0 総記 … 9 文学. Divisions (綱目, two digits), sections
(要目, three digits) and anything finer are deliberately not bundled; look
those up in the printed schedules or a library service.

The ten main classes are the same in NDC 8, 9 and 10, so the label does not
depend on which edition a record used.
"""
from __future__ import annotations

import re
from typing import NamedTuple, Optional

__all__ = ["NdcClass", "ndc_class", "NDC_MAIN_CLASSES"]

#: First digit → (Japanese label, English label), NDC 新訂10版 第1次区分表.
NDC_MAIN_CLASSES = {
    "0": ("総記", "General works"),
    "1": ("哲学", "Philosophy"),
    "2": ("歴史", "History"),
    "3": ("社会科学", "Social sciences"),
    "4": ("自然科学", "Natural sciences"),
    "5": ("技術", "Technology"),
    "6": ("産業", "Industry"),
    "7": ("芸術", "The arts"),
    "8": ("言語", "Language"),
    "9": ("文学", "Literature"),
}

_FULLWIDTH = str.maketrans("０１２３４５６７８９．：　ＮＤＣｎｄｃ", "0123456789.: NDCndc")
# "913.6", "913", "9", optionally after "NDC:", "NDC10:", "NDC9 " … A prefix
# needs a separator: "NDC913.6" or "NDC10" alone are ambiguous.
_MARK = re.compile(r"(?:ndc\d{0,2}\s*[:\s]\s*)?(\d{1,3}(?:\.\d+)?)", re.I)


class NdcClass(NamedTuple):
    """An NDC mark and the label of its main class."""

    code: str
    main: str
    label: str
    label_en: str


def ndc_class(raw: Optional[str]) -> Optional[NdcClass]:
    """Return the main class of an NDC mark such as ``"913.6"``.

    Accepts one to three digits with an optional decimal part, full-width
    digits, and an optional ``NDC:`` / ``NDC10:`` / ``NDC9 `` prefix. Returns ``None`` for
    anything else (letters like library shelf prefixes, ranges, empty input).

    >>> ndc_class("913.6")
    NdcClass(code='913.6', main='9', label='文学', label_en='Literature')
    >>> ndc_class("NDC10:007.64").label
    '総記'
    >>> ndc_class("９１３．６").code
    '913.6'
    >>> ndc_class("K913") is None
    True
    """
    s = (raw or "").strip().translate(_FULLWIDTH)
    m = _MARK.fullmatch(s)
    if not m or not m.group(1).isascii():
        return None
    code = m.group(1)
    ja, en = NDC_MAIN_CLASSES[code[0]]
    return NdcClass(code, code[0], ja, en)
