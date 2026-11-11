"""Export a ``Book`` to BibTeX, RIS or CSL-JSON.

These three formats are small, stable text mappings of a handful of fields
(title, author, publisher, year, ISBN). Existing converters — bibtexparser,
pybtex, rispy, citeproc-py, betterbib, commonmeta-py — either parse rather
than generate, pull in lxml or a full CSL processor, or want a newer Python
than hondana supports. Since hondana is dependency-free and ``Book`` is a
flat record, the exporters live here as plain functions.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Sequence, Union

from .isbn import hyphenate
from .lookup import Book

__all__ = ["to_bibtex", "to_ris", "to_csl", "dumps", "FORMATS"]

FORMATS = ("bibtex", "ris", "csl")

# Role words that openBD / NDL often glue onto the author field.
_ROLE_TOKEN = re.compile(
    r"^(?:著|編|訳|監修|編集|編著|共著|共編|作|撰)$"
)
_ROLE_SUFFIX = re.compile(
    r"(?:著|編|訳|監修|編集|編著|共著|共編|作|撰)$"
)
# Split author lists. "and" is the BibTeX separator; Japanese sources use
# enumerators and a full-width slash (「夏目漱石／著」).
_AUTHOR_SPLIT = re.compile(r"\s*(?:、|，|;|／|/|\band\b)\s*")
_WESTERN_NAME = re.compile(r"^([^,]+),\s+(.+)$")
_YEAR = re.compile(r"(\d{4})")

# LaTeX specials. Backslash first so we don't double-escape the escapes.
_BIBTEX_SPECIALS = (
    ("\\", r"\textbackslash{}"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("$", r"\$"),
    ("%", r"\%"),
    ("&", r"\&"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
)


def _year(book: Book) -> str:
    m = _YEAR.search(book.year or "")
    return m.group(1) if m else ""


def _isbn(book: Book) -> str:
    return hyphenate(book.isbn) or book.isbn


def citation_key(book: Book) -> str:
    """ASCII-safe, unique-enough key: ``isbn`` plus the 13 digits, or a fallback."""
    digits = re.sub(r"\D", "", book.isbn or "")
    if digits:
        return "isbn" + digits
    slug = re.sub(r"[^A-Za-z0-9]+", "", (book.title or "book"))[:24] or "book"
    return slug + (_year(book) or "")


def split_authors(author: str) -> List[str]:
    """Split a source author string into individual names, dropping role words."""
    text = (author or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in _AUTHOR_SPLIT.split(text) if p.strip()]
    out: List[str] = []
    for p in parts:
        if _ROLE_TOKEN.match(p):
            continue
        p = _ROLE_SUFFIX.sub("", p).strip()
        if p:
            out.append(p)
    return out


def _csl_name(name: str) -> Dict[str, str]:
    m = _WESTERN_NAME.match(name)
    if m:
        return {"family": m.group(1), "given": m.group(2)}
    return {"literal": name}


def _bibtex_escape(value: str) -> str:
    for src, dst in _BIBTEX_SPECIALS:
        value = value.replace(src, dst)
    return value


def _bibtex_field(name: str, value: str) -> str:
    return f"  {name} = {{{_bibtex_escape(value)}}}"


def to_bibtex(book: Book) -> str:
    """Render one book as a UTF-8 BibTeX ``@book`` entry."""
    fields = [_bibtex_field("title", book.title)] if book.title else []
    authors = split_authors(book.author)
    if authors:
        fields.append(_bibtex_field("author", " and ".join(authors)))
    if book.publisher:
        fields.append(_bibtex_field("publisher", book.publisher))
    year = _year(book)
    if year:
        fields.append(_bibtex_field("year", year))
    isbn = _isbn(book)
    if isbn:
        fields.append(_bibtex_field("isbn", isbn))
    body = ",\n".join(fields)
    return f"@book{{{citation_key(book)},\n{body}\n}}\n"


def to_ris(book: Book) -> str:
    """Render one book as a RIS record (``TY BOOK`` … ``ER``)."""
    lines = ["TY  - BOOK"]
    if book.title:
        lines.append(f"TI  - {book.title}")
    for name in split_authors(book.author):
        lines.append(f"AU  - {name}")
    if book.publisher:
        lines.append(f"PB  - {book.publisher}")
    year = _year(book)
    if year:
        lines.append(f"PY  - {year}")
    isbn = _isbn(book)
    if isbn:
        lines.append(f"SN  - {isbn}")
    lines.append("ER  - ")
    return "\n".join(lines) + "\n"


def to_csl(book: Book) -> Dict[str, Any]:
    """Return one book as a CSL-JSON item (a plain dict, not a string)."""
    item: Dict[str, Any] = {"id": citation_key(book), "type": "book"}
    if book.title:
        item["title"] = book.title
    authors = split_authors(book.author)
    if authors:
        item["author"] = [_csl_name(n) for n in authors]
    if book.publisher:
        item["publisher"] = book.publisher
    year = _year(book)
    if year:
        item["issued"] = {"date-parts": [[int(year)]]}
    isbn = _isbn(book)
    if isbn:
        item["ISBN"] = isbn
    return item


def dumps(books: Union[Book, Iterable[Book]], fmt: str) -> str:
    """Serialise one book or a sequence to ``bibtex``, ``ris`` or ``csl``.

    CSL-JSON is a single object for one book and a JSON array for many,
    matching the CLI's existing JSON behaviour.
    """
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt!r} (expected {', '.join(FORMATS)})")
    items: Sequence[Book] = [books] if isinstance(books, Book) else list(books)
    if fmt == "bibtex":
        return "".join(to_bibtex(b) for b in items)
    if fmt == "ris":
        return "\n".join(to_ris(b) for b in items)
    payload: Union[Dict[str, Any], List[Dict[str, Any]]] = to_csl(items[0]) if len(items) == 1 else [to_csl(b) for b in items]
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
