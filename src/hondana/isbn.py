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
    """Return the ISBN-13 form, or ``""``.

    ISBN-10 input is prefixed with ``978``. With ``strict=False`` (default) a
    wrong check digit is repaired — catalogue data often has typos; with
    ``strict=True`` it is rejected.

    >>> to_isbn13("4-00-310101-4")
    '9784003101018'
    >>> to_isbn13("9784003101019")          # repaired
    '9784003101018'
    >>> to_isbn13("9784003101019", strict=True)
    ''
    """
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


def to_isbn10(raw: str | None, *, strict: bool = False) -> str:
    """Return the ISBN-10 form, or ``""``.

    Only ``978…`` ISBN-13 values convert (``979…`` has no ISBN-10 equivalent).
    ``strict`` mirrors ``to_isbn13``: repair a wrong check digit by default,
    reject it when ``strict=True``.

    >>> to_isbn10("978-4-00-310101-8")
    '4003101014'
    >>> to_isbn10("080442957X")
    '080442957X'
    >>> to_isbn10("9784003101019", strict=True)
    ''
    >>> to_isbn10("9791032300824")
    ''
    """
    if strict and not is_valid(raw):
        return ""
    s = to_isbn13(raw, strict=strict)
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


# Registrant and registration-group ranges, derived from the ISBN International
# Agency's RangeMessage.xml by scripts/update_isbn_ranges.py (the XML itself is
# not vendored). Length 0 means the range is unassigned; those ISBNs are not
# hyphenated. Re-run the script to refresh the tables when the agency updates
# them. isbnlib ships a similar table; we generate our own to stay dependency-free.
from ._isbn_ranges import GROUP_RULES, REGISTRANT_RULES


def _parse_rules(text: str) -> tuple[tuple[str, str, int], ...]:
    out: list[tuple[str, str, int]] = []
    if not text:
        return ()
    for part in text.split(","):
        rng, _, length = part.partition(":")
        lo, _, hi = rng.partition("-")
        out.append((lo, hi, int(length)))
    return tuple(out)


_GROUP = {p: _parse_rules(t) for p, t in GROUP_RULES.items()}
_REGISTRANT = {g: _parse_rules(t) for g, t in REGISTRANT_RULES.items()}


def _rule_length(rules: tuple[tuple[str, str, int], ...], body7: str) -> int | None:
    for lo, hi, n in rules:
        if lo <= body7 <= hi:
            return n
    return None


def hyphenate(raw: str | None) -> str:
    """Hyphenate an ISBN-13 by registration group and registrant code, e.g.
    ``978-4-00-310101-8``. Covers every group in the current ISBN range
    message, including 978-2, 978-3, 978-89 and the 979-… prefixes. Returns
    ``""`` for invalid ISBNs and unassigned ranges.

    >>> hyphenate("4003101014")
    '978-4-00-310101-8'
    >>> hyphenate("9784873117782")
    '978-4-87311-778-2'
    >>> hyphenate("0131103628")
    '978-0-13-110362-7'
    >>> hyphenate("9787020002207")
    '978-7-02-000220-7'
    >>> hyphenate("9783161484100")
    '978-3-16-148410-0'
    >>> hyphenate("9791032300824")
    '979-10-323-0082-4'
    """
    s = to_isbn13(raw, strict=True)
    if len(s) != 13:
        return ""
    prefix = s[:3]
    group_rules = _GROUP.get(prefix)
    if not group_rules:
        return ""
    group_len = _rule_length(group_rules, s[3:10])
    if not group_len:
        return ""
    group = s[3:3 + group_len]
    rest = s[3 + group_len:12]
    body7 = (rest + "0000000")[:7]
    registrant_rules = _REGISTRANT.get(f"{prefix}-{group}")
    if not registrant_rules:
        return ""
    registrant_len = _rule_length(registrant_rules, body7)
    if not registrant_len:
        return ""
    return f"{prefix}-{group}-{rest[:registrant_len]}-{rest[registrant_len:]}-{s[12]}"
