"""ISBN helpers: clean, validate, convert."""
from __future__ import annotations

import re

__all__ = ["clean", "is_valid", "to_isbn13", "to_isbn10", "find_isbns"]

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


def find_isbns(text: str) -> list[str]:
    """Pull every valid ISBN out of free text, normalised to ISBN-13, de-duplicated."""
    out: list[str] = []
    for m in _FIND.finditer(text or ""):
        s = clean(m.group(1))
        if is_valid(s):
            i = to_isbn13(s)
            if i not in out:
                out.append(i)
    return out
