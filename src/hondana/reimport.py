"""Read back the BibTeX, RIS and CSL-JSON that :mod:`hondana.export` writes.

This is deliberately *not* a general parser. It reads the fields hondana
exports — title, author, publisher, year, ISBN, and when present the metadata
licence and 出典 credit line — from files hondana (or a
reference manager writing the same simple shapes) produced, so a reading list
can go ``lookup → .bib → edit → back into Book``. For arbitrary BibTeX
(``@string`` macros, ``#`` concatenation, crossref, LaTeX accents) use
bibtexparser or pybtex; for every RIS tag use rispy; for full CSL use
citeproc-py. Those are all heavier than this module needs to be.

What is understood:

* BibTeX: any ``@type{key, …}`` entry (``@comment`` / ``@string`` /
  ``@preamble`` are skipped), values in ``{…}`` (nested braces ok), ``"…"`` or
  bare numbers; ``author`` split on ``and``; the escapes ``to_bibtex`` writes
  are undone and remaining case-protecting braces dropped; ``copyright`` is
  the metadata licence, ``note`` the credit line.
* RIS: ``TY`` … ``ER`` records; ``TI``/``T1``, ``AU``/``A1``, ``PB``,
  ``PY``/``Y1``/``DA`` (year taken from the first four digits), ``SN``;
  ``N1`` is the credit line, except a line ``Licence:`` / ``License:`` which
  is the metadata licence.
* CSL-JSON: one item or an array; ``title``, ``author`` (``literal`` or
  ``family`` + ``given``), ``publisher``, ``issued`` (``date-parts``, ``raw``
  or ``literal``), ``ISBN``; ``license`` (or ``licence``) is the metadata
  licence, ``note`` the credit line.

Several authors are joined with ``"; "`` — :func:`hondana.export.split_authors`
splits on it, so ``dumps(loads(text))`` gives the same authors back. ISBNs
that check out are stored as 13 digits like the lookup sources do; anything
else is kept as written. ``Book.source`` is the format name.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .isbn import is_valid, to_isbn13
from .lookup import Book

__all__ = ["from_bibtex", "from_ris", "from_csl", "loads", "sniff"]

_YEAR = re.compile(r"\d{4}")
_RIS_LINE = re.compile(r"^([A-Z][A-Z0-9])  -(?: (.*))?$")
# Matches the ``Licence:`` prefix :data:`hondana.export.RIS_LICENCE_PREFIX`
# writes, and the American spelling.
_RIS_LICENCE = re.compile(r"^(?:Licence|License)\s*:\s*(.+)$")
_BIBTEX_SKIP = {"comment", "string", "preamble"}

# The inverse of export._BIBTEX_SPECIALS (plus the brace-less forms of the two
# text commands, which BibTeX tools also write).
_BIBTEX_UNESCAPE = (
    (r"\textbackslash{}", "\x00"),
    (r"\textbackslash", "\x00"),
    (r"\textasciitilde{}", "~"),
    (r"\textasciitilde", "~"),
    (r"\textasciicircum{}", "^"),
    (r"\textasciicircum", "^"),
    (r"\{", "\x01"),
    (r"\}", "\x02"),
    (r"\$", "$"),
    (r"\%", "%"),
    (r"\&", "&"),
    (r"\#", "#"),
    (r"\_", "_"),
)


def _isbn(value: str) -> str:
    value = (value or "").strip()
    # RIS / CSL may carry several ISBNs ("978… 978…", "978…; 978…"); keep the first.
    first = re.split(r"[\s;,]+", value)[0] if value else ""
    if first and is_valid(first):
        return to_isbn13(first)
    return value


def _year(value: str) -> str:
    m = _YEAR.search(value or "")
    return m.group(0) if m else ""


def _credits_from_n1(notes: List[str]) -> tuple[str, str]:
    """Split RIS ``N1`` lines into (licence, attribution)."""
    licence, lines = "", []
    for value in notes:
        m = _RIS_LICENCE.match(value)
        if m and not licence:
            licence = m.group(1).strip()
        else:
            lines.append(value)
    return licence, "\n".join(lines)


def _book(
    fmt: str,
    title: str,
    authors: List[str],
    publisher: str,
    year: str,
    isbn: str,
    licence: str = "",
    attribution: str = "",
) -> Book:
    return Book(
        isbn=_isbn(isbn),
        title=title.strip(),
        author="; ".join(a.strip() for a in authors if a.strip()),
        publisher=publisher.strip(),
        year=_year(year),
        source=fmt,
        licence=(licence or "").strip(),
        attribution=(attribution or "").strip(),
    )


# --- BibTeX -----------------------------------------------------------------

def _bibtex_unescape(value: str) -> str:
    for src, dst in _BIBTEX_UNESCAPE:
        value = value.replace(src, dst)
    # Remaining braces only protect case ({NHK}); drop them.
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\s+", " ", value).strip()
    return value.replace("\x00", "\\").replace("\x01", "{").replace("\x02", "}")


def _braced(text: str, i: int, close: str) -> tuple[str, int]:
    """Read from just after an opening ``{`` or ``"`` to its partner."""
    depth, start = 0, i
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            if depth == 0 and close == "}":
                return text[start:i], i + 1
            depth -= 1
        elif ch == '"' and close == '"' and depth == 0:
            return text[start:i], i + 1
        i += 1
    raise ValueError("unterminated BibTeX value")


def _bibtex_fields(body: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    i = 0
    field_re = re.compile(r"\s*,?\s*([A-Za-z][\w\-:.]*)\s*=\s*")
    while i < len(body):
        m = field_re.match(body, i)
        if not m:
            break
        name, i = m.group(1).lower(), m.end()
        if i >= len(body):
            break
        if body[i] == "{":
            raw, i = _braced(body, i + 1, "}")
        elif body[i] == '"':
            raw, i = _braced(body, i + 1, '"')
        else:
            n = re.match(r"[^,}\s]*", body[i:])
            raw = n.group(0) if n else ""
            i += len(raw)
        fields.setdefault(name, _bibtex_unescape(raw))
    return fields


def from_bibtex(text: str) -> List[Book]:
    """Books from BibTeX entries (the subset ``to_bibtex`` writes; see module doc)."""
    books: List[Book] = []
    i = 0
    head = re.compile(r"@\s*([A-Za-z]+)\s*([{(])")
    while True:
        m = head.search(text, i)
        if not m:
            break
        kind, opener = m.group(1).lower(), m.group(2)
        body, i = _braced(text, m.end(), "}") if opener == "{" else _paren(text, m.end())
        if kind in _BIBTEX_SKIP:
            continue
        # Drop the citation key ("isbn978…,").
        key_end = body.find(",")
        fields = _bibtex_fields(body[key_end + 1:] if key_end >= 0 else "")
        authors = re.split(r"\s+and\s+", fields.get("author", "")) if fields.get("author") else []
        books.append(_book(
            "bibtex", fields.get("title", ""), authors, fields.get("publisher", ""),
            fields.get("year", "") or fields.get("date", ""), fields.get("isbn", ""),
            fields.get("copyright", ""), fields.get("note", ""),
        ))
    return books


def _paren(text: str, i: int) -> tuple[str, int]:
    end = text.find(")", i)
    if end < 0:
        raise ValueError("unterminated BibTeX entry")
    # @entry( … ) is legal BibTeX; good enough as long as no value contains ")".
    return text[i:end], end + 1


# --- RIS --------------------------------------------------------------------

def from_ris(text: str) -> List[Book]:
    """Books from RIS records (``TY`` … ``ER``), reading the tags ``to_ris`` writes."""
    books: List[Book] = []
    rec: Optional[Dict[str, List[str]]] = None
    for line in text.lstrip("\ufeff").splitlines():
        m = _RIS_LINE.match(line.rstrip("\r"))
        if not m:
            continue
        tag, value = m.group(1), (m.group(2) or "").strip()
        if tag == "TY":
            rec = {}
            continue
        if rec is None:
            continue
        if tag == "ER":
            books.append(_ris_book(rec))
            rec = None
            continue
        if value:
            rec.setdefault(tag, []).append(value)
    return books


def _ris_book(rec: Dict[str, List[str]]) -> Book:
    def first(*tags: str) -> str:
        for t in tags:
            if rec.get(t):
                return rec[t][0]
        return ""
    authors = rec.get("AU", []) + rec.get("A1", [])
    licence, attribution = _credits_from_n1(rec.get("N1", []))
    return _book(
        "ris", first("TI", "T1"), authors, first("PB"), first("PY", "Y1", "DA"), first("SN"),
        licence, attribution,
    )


# --- CSL-JSON ---------------------------------------------------------------

def _csl_author(name: Any) -> str:
    if not isinstance(name, dict):
        return str(name or "")
    if name.get("literal"):
        return str(name["literal"])
    family, given = str(name.get("family") or ""), str(name.get("given") or "")
    return f"{family}, {given}" if family and given else family or given


def _csl_year(issued: Any) -> str:
    if not isinstance(issued, dict):
        return str(issued or "")
    parts = issued.get("date-parts")
    if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
        return str(parts[0][0])
    return str(issued.get("raw") or issued.get("literal") or "")


def from_csl(data: Any) -> List[Book]:
    """Books from CSL-JSON: a JSON string, one item dict, or a list of items."""
    if isinstance(data, (str, bytes)):
        data = json.loads(data)
    items = [data] if isinstance(data, dict) else list(data or [])
    books: List[Book] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("CSL-JSON items must be objects")
        authors = [_csl_author(a) for a in item.get("author") or []]
        books.append(_book(
            "csl", str(item.get("title") or ""), authors, str(item.get("publisher") or ""),
            _csl_year(item.get("issued")), str(item.get("ISBN") or ""),
            str(item.get("license") or item.get("licence") or ""),
            str(item.get("note") or ""),
        ))
    return books


# --- dispatch ---------------------------------------------------------------

def sniff(text: str) -> str:
    """Guess ``bibtex`` / ``ris`` / ``csl`` from the first non-blank character(s)."""
    s = text.lstrip("\ufeff \t\r\n")
    if s[:1] in ("[", "{"):
        return "csl"
    ris = re.search(r"^TY  -", s, re.M)
    bib = re.search(r"^\s*@\s*[A-Za-z]+\s*[{(]", s, re.M)
    if ris and (not bib or ris.start() < bib.start()):
        return "ris"
    if bib:
        return "bibtex"
    raise ValueError("cannot tell the format (expected BibTeX, RIS or CSL-JSON)")


def loads(text: str, fmt: Optional[str] = None) -> List[Book]:
    """Parse ``text`` as ``bibtex``, ``ris`` or ``csl`` (guessed when ``fmt`` is None).

    The inverse of :func:`hondana.export.dumps` for the fields it writes
    (including licence and attribution when present);
    always returns a list, even for a single CSL object.
    """
    fmt = fmt or sniff(text)
    if fmt == "bibtex":
        return from_bibtex(text)
    if fmt == "ris":
        return from_ris(text)
    if fmt == "csl":
        return from_csl(text)
    raise ValueError(f"unknown format: {fmt!r} (expected bibtex, ris, csl)")
