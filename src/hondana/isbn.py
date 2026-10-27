"""ISBN helpers: clean, validate, convert."""
from __future__ import annotations

import re
import unicodedata

__all__ = ["clean", "is_valid", "to_isbn13", "to_isbn10", "find_isbns", "hyphenate"]

_NON = re.compile(r"[^0-9Xx]")


def clean(raw: str | None) -> str:
    return _NON.sub("", raw or "").upper()


def _check13(core12: str) -> str:
    return str((10 - sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core12)) % 10) % 10)


def _check10(core9: str) -> str:
    r = (11 - sum(int(c) * (10 - i) for i, c in enumerate(core9)) % 11) % 11
    return "X" if r == 10 else str(r)


def is_valid(raw: str | None) -> bool:
    s = clean(raw)
    if len(s) == 13 and s.isdigit() and s[:3] in ("978", "979"):
        return _check13(s[:12]) == s[12]
    if len(s) == 10 and s[:9].isdigit():
        return _check10(s[:9]) == s[9]
    return False


def to_isbn13(raw: str | None, *, strict: bool = False) -> str:
    """Return the ISBN-13 form, or ``""``. With ``strict=False`` a wrong check
    digit is repaired (catalogue data has typos); with ``strict=True`` it is rejected."""
    s = clean(raw)
    if strict and not is_valid(s):
        return ""
    if len(s) == 10 and s[:9].isdigit():
        core = "978" + s[:9]
    elif len(s) == 13 and s.isdigit():
        core = s[:12]
    else:
        return ""
    return core + _check13(core)


def to_isbn10(raw: str | None) -> str:
    s = to_isbn13(raw)
    if not s.startswith("978"):
        return ""
    return s[3:12] + _check10(s[3:12])


_FIND = re.compile(r"(?<![0-9])(97[89][\d\- ]{10,14}|[\d][\d\- ]{8,11}[\dXx])(?![0-9])")


# Dashes that show up between ISBN groups in Japanese text and PDFs.
_DASHES = str.maketrans(dict.fromkeys("‐‑‒–—―−", "-"))


def find_isbns(text: str) -> list[str]:
    """Pull every valid ISBN out of free text, normalised to ISBN-13, de-duplicated.

    Full-width digits (「９７８－４…」) and typographic dashes (‐ – − …) are accepted:

    >>> find_isbns("ＩＳＢＮ９７８－４－００－３１０１０１－８、ISBN-10:4003101014")
    ['9784003101018']
    """
    out: list[str] = []
    for m in _FIND.finditer(unicodedata.normalize("NFKC", text or "").translate(_DASHES)):
        s = clean(m.group(1))
        if is_valid(s):
            i = to_isbn13(s)
            if i not in out:
                out.append(i)
    return out


# Registrant (publisher) ranges for group 978-4 (Japan), from the ISBN International
# range message: the first digits after "4" decide how long the publisher code is.
_JP_RANGES = (("00", "19"), ("200", "699"), ("7000", "8499"), ("85000", "89999"), ("900000", "949999"), ("9500000", "9999999"))


def hyphenate(raw: str | None) -> str:
    """Hyphenate a Japanese ISBN-13 (978-4) by publisher code, e.g.
    ``978-4-00-310101-8``. Returns ``""`` for invalid ISBNs and for other
    groups, which aren't covered yet.

    >>> hyphenate("4003101014")
    '978-4-00-310101-8'
    >>> hyphenate("9784873117782")
    '978-4-87311-778-2'
    """
    s = to_isbn13(raw, strict=True)
    if not s.startswith("9784"):
        return ""
    body = s[4:12]
    for lo, hi in _JP_RANGES:
        if lo <= body[: len(lo)] <= hi:
            n = len(lo)
            return f"978-4-{body[:n]}-{body[n:]}-{s[12]}"
    return ""
