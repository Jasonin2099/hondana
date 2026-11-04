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


# Registrant (publisher) ranges per registration group, transcribed from the ISBN
# International range message (RangeMessage.xml; the China/Taiwan groups were
# cross-checked against isbnlib's copy). Within a group the first digits after the group number decide how long the registrant code is.
# Unassigned gaps are left out, so ISBNs falling there are not hyphenated.
_RANGE_TEXT = {
    "0": (  # English language
        "00-19,200-227,2280-2289,229-368,3690-3699,370-638,6390-6397,"
        "6398000-6399999,640-644,6450000-6459999,646-647,6480000-6489999,649-654,"
        "6550-6559,656-699,7000-8499,85000-89999,900000-900370,9003710-9003719,"
        "900372-949999,9500000-9999999"
    ),
    "1": (  # English language
        "000-009,01-02,030-034,0350-0399,040-047,0480-0499,05-05,0670000-0699999,"
        "0700-0999,100-397,3980-5499,55000-64999,6500-6799,68000-68599,6860-7139,"
        "714-716,7170-7319,7320000-7399999,74000-76199,7620-7634,7635000-7649999,"
        "76500-77499,7750000-7753999,77540-77639,7764000-7764999,77650-77699,"
        "7770000-7782999,77830-78999,7900-7999,80000-80049,80050-80499,"
        "80500-83799,8380000-8384999,83850-86719,8672-8675,86760-86979,"
        "869800-915999,9160000-9165059,916506-916869,9168700-9169079,"
        "916908-919163,9191640-9195649,919565-919599,9196000-9196549,"
        "919655-972999,9730-9877,987800-991149,9911500-9911999,991200-998989,"
        "9989900-9999999"
    ),
    "4": (  # Japan
        "00-19,200-699,7000-8499,85000-89999,900000-949999,9500000-9999999"
    ),
    "7": (  # China (mainland)
        "00-09,100-499,5000-7999,80000-89999,900000-999999"
    ),
    "957": (  # Taiwan
        "00-02,0300-0499,05-19,2000-2099,21-27,28000-30999,31-43,440-819,"
        "8200-9699,97000-99999"
    ),
    "986": (  # Taiwan
        "00-05,06000-06999,0700-0799,08-11,120-539,5400-7999,80000-99999"
    ),
}


def _parse_ranges(text: str) -> tuple[tuple[str, str], ...]:
    pairs = (r.split("-") for r in text.split(","))
    return tuple((lo, hi) for lo, hi in pairs)


_RANGES = {g: _parse_ranges(t) for g, t in _RANGE_TEXT.items()}


def hyphenate(raw: str | None) -> str:
    """Hyphenate an ISBN-13 by registration group and registrant code, e.g.
    ``978-4-00-310101-8``. Covers 978-0 / 978-1 (English language), 978-4
    (Japan), 978-7 (China) and 978-957 / 978-986 (Taiwan). Returns ``""`` for
    invalid ISBNs, other groups and unassigned ranges.

    >>> hyphenate("4003101014")
    '978-4-00-310101-8'
    >>> hyphenate("9784873117782")
    '978-4-87311-778-2'
    >>> hyphenate("0131103628")
    '978-0-13-110362-7'
    >>> hyphenate("9787020002207")
    '978-7-02-000220-7'
    """
    s = to_isbn13(raw, strict=True)
    if not s.startswith("978"):
        return ""
    # Group codes are prefix-free, so at most one of these matches.
    group = next((g for g in _RANGES if s[3:].startswith(g)), None)
    if group is None:
        return ""
    ranges = _RANGES[group]
    body = s[3 + len(group):12]
    for lo, hi in ranges:
        if lo <= body[: len(lo)] <= hi:
            n = len(lo)
            return f"978-{group}-{body[:n]}-{body[n:]}-{s[12]}"
    return ""
