"""python -m hondana fold|isbn|lookup|dedupe …

  fold   — print the matching key for some text
  isbn   — find, validate and hyphenate ISBNs in text (no network)
  lookup — look ISBNs up across openBD / NDL / Google Books / Open Library
  dedupe — report (or drop) duplicate rows in a book-list CSV
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional, Sequence

from .isbn import find_isbns, hyphenate, is_valid, to_isbn13
from .export import dumps
from .lookup import Book
from .dedupe import _AUTHOR_ALIASES, _ISBN_ALIASES, _TITLE_ALIASES, dedupe, resolve_field
from . import fold, fold_steps, lookup_many


def _read_text(args_text: Sequence[str]) -> str:
    """Join argv text, or fall back to stdin when none was given."""
    if args_text:
        return " ".join(args_text)
    return sys.stdin.read()


def _cmd_fold(a: argparse.Namespace) -> int:
    opts = {
        "kana": False if a.kana == "off" else a.kana,
        "small_kana": a.small_kana,
        "iteration_marks": a.iteration_marks,
        "itaiji": a.itaiji,
        "dashes": a.dashes,
    }
    text = " ".join(a.text)
    if not a.explain:
        print(fold(text, **opts))
        return 0
    steps = fold_steps(text, **opts)
    w = max([len("input")] + [len(n) for n, _ in steps])
    print(f"{'input':<{w}}  {text}")
    prev = text
    for name, s in steps:
        print(f"{name:<{w}}  {s}" + ("" if s != prev else "  (no change)"))
        prev = s
    return 0


def _cmd_isbn(a: argparse.Namespace) -> int:
    text = _read_text(a.text).strip()
    if not text:
        print("no input", file=sys.stderr)
        return 1

    # Single token → validate / hyphenate that candidate.
    # Multi-word text (or --find) → scan with find_isbns.
    single = (not a.find) and len(text.split()) == 1
    if single:
        valid = is_valid(text)
        isbn13 = to_isbn13(text, strict=True) if valid else ""
        hyp = hyphenate(text) if valid else ""
        if a.json:
            print(json.dumps(
                {"isbn": text, "isbn13": isbn13, "hyphenated": hyp, "valid": valid},
                ensure_ascii=False,
            ))
        elif a.validate:
            print("ok" if valid else "invalid")
        else:
            if not valid:
                print("invalid", file=sys.stderr)
                return 1
            print(hyp or isbn13)
        return 0 if valid else 1

    found = find_isbns(text)
    rows = [{"isbn13": i, "hyphenated": hyphenate(i) or i, "valid": True} for i in found]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif a.validate:
        if not rows:
            print("none", file=sys.stderr)
            return 1
        for r in rows:
            print(f"{r['hyphenated']}\tok")
    else:
        for r in rows:
            print(r["hyphenated"])
    return 0 if rows else 1


def _format_table(books: list[Book]) -> str:
    cols = ("isbn", "title", "author", "publisher", "year", "source")
    rows = [[(getattr(b, c) or "") for c in cols] for b in books]
    widths = [len(c) for c in cols]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], min(len(cell), 40))
    def clip(s: str, w: int) -> str:
        return s if len(s) <= w else s[: w - 1] + "…"
    head = "  ".join(c.upper().ljust(widths[i]) for i, c in enumerate(cols))
    lines = [head, "  ".join("-" * w for w in widths)]
    for row in rows:
        lines.append("  ".join(clip(cell, widths[i]).ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def _cmd_lookup(a: argparse.Namespace) -> int:
    isbns = list(a.isbn) or _read_text(()).split()
    if not isbns:
        print("no ISBN given", file=sys.stderr)
        return 1
    books = lookup_many(
        isbns,
        merge=a.merge,
        rate=a.rate,
        on_error=lambda n, e: print(f"# {n}: {type(e).__name__}", file=sys.stderr),
    )
    found = [b for b in books if b]
    missing = [isbn for isbn, b in zip(isbns, books) if b is None]
    for m in missing:
        print(f"not found: {m}", file=sys.stderr)

    fmt = a.format
    if fmt is None:
        fmt = "json" if len(isbns) == 1 else "table"

    if found:
        if fmt == "json":
            payload = found[0].to_dict() if len(isbns) == 1 else [b.to_dict() for b in found]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif fmt in ("bibtex", "ris", "csl"):
            # dumps already ends with a newline; avoid print()'s extra one.
            sys.stdout.write(dumps(found if len(isbns) > 1 else found[0], fmt))
        else:
            print(_format_table(found))

    if not found:
        return 1
    return 1 if missing else 0


def _cmd_dedupe(a: argparse.Namespace) -> int:
    import csv
    from pathlib import Path

    source = a.file
    close = False
    if source is None or source == "-":
        stream = sys.stdin
    else:
        stream = open(source, encoding="utf-8-sig", newline="")
        close = True
    try:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            print("no CSV header", file=sys.stderr)
            return 1
        rows = list(reader)
    finally:
        if close:
            stream.close()

    try:
        result = dedupe(rows, isbn_field=a.isbn, title_field=a.title, author_field=a.author)
    except KeyError as e:
        print(str(e), file=sys.stderr)
        return 1

    isbn_f = resolve_field(rows, _ISBN_ALIASES, a.isbn) if rows else a.isbn
    title_f = resolve_field(rows, _TITLE_ALIASES, a.title) if rows else a.title
    author_f = resolve_field(rows, _AUTHOR_ALIASES, a.author) if rows else a.author

    if a.unique is not None or a.output:
        dest = a.output or a.unique or "-"
        close_out = False
        if dest == "-":
            out = sys.stdout
        else:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            out = open(dest, "w", encoding="utf-8", newline="")
            close_out = True
        try:
            fields = list(rows[0].keys()) if rows else ["title", "author", "isbn"]
            writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(result.unique)
        finally:
            if close_out:
                out.close()
        print(
            f"{len(result)} unique / {len(rows)} rows ({result.extra} dropped)",
            file=sys.stderr,
        )
        return 0

    if a.json:
        groups = result.groups if a.all else result.duplicate_groups
        payload = {
            "rows": len(rows),
            "unique": len(result),
            "extra": result.extra,
            "groups": [
                {"kind": g.kind, "key": list(g.key), "count": len(g.rows), "rows": [dict(r) for r in g.rows]}
                for g in groups
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    dups = result.duplicate_groups
    if not dups:
        print(f"{len(rows)} rows, no duplicates")
        return 0

    def cells(row: dict[str, str]) -> str:
        parts = [
            str(row.get(title_f) or "").strip() if title_f else "",
            str(row.get(author_f) or "").strip() if author_f else "",
            str(row.get(isbn_f) or "").strip() if isbn_f else "",
        ]
        return " / ".join(p for p in parts if p) or "(empty)"

    for i, g in enumerate(dups, 1):
        label = f"isbn {g.isbn}" if g.kind == "isbn" else "title+author"
        print(f"group {i} ({label}), {len(g.rows)} rows")
        for row in g.rows:
            print(f"  {cells(dict(row))}")
    print(f"{len(result)} unique, {len(dups)} duplicate groups ({result.extra} extra rows)")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="hondana")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fold", help="print the matching key for some text")
    f.add_argument("text", nargs="+")
    f.add_argument("--explain", action="store_true", help="print the result of every step")
    f.add_argument("--kana", choices=("hira", "kata", "off"), default="hira",
                   help="fold kana to hiragana (default), katakana, or leave them alone")
    f.add_argument("--small-kana", action="store_true", help="also fold small kana (ぁ→あ, っ→つ)")
    f.add_argument("--iteration-marks", choices=("expand", "drop"), help="handle 々 ゝ ゞ")
    f.add_argument("--itaiji", action="store_true", help="fold variant kanji in names (髙→高, 﨑→崎)")
    f.add_argument("--dashes", action="store_true", help="unify long-vowel marks, tildes and dashes (コ─ヒ─→コーヒー)")

    i = sub.add_parser(
        "isbn",
        help="find, validate and hyphenate ISBNs in text (no network)",
    )
    i.add_argument("text", nargs="*", help="ISBN or free text; reads stdin when omitted")
    i.add_argument("--find", action="store_true", help="always scan text with find_isbns()")
    i.add_argument("--validate", action="store_true", help="print ok/invalid instead of hyphenating")
    i.add_argument("--hyphenate", action="store_true", help="explicit hyphenate (default for a bare ISBN)")
    i.add_argument("--json", action="store_true", help="structured JSON output")

    l = sub.add_parser(
        "lookup",
        help="look ISBNs up (openBD → NDL → Google Books → Open Library)",
    )
    l.add_argument("isbn", nargs="*", help="one or more ISBNs; reads them from stdin when omitted")
    l.add_argument("--rate", type=float, default=0.5, metavar="SECONDS",
                   help="minimum seconds between lookups (default 0.5; be kind to free APIs)")
    l.add_argument("--merge", action="store_true", help="fill missing fields from later sources")
    l.add_argument(
        "--format", choices=("json", "table", "bibtex", "ris", "csl"), default=None,
        help="output format (default: json for one ISBN, table for many)",
    )


    d = sub.add_parser(
        "dedupe",
        help="report duplicate rows in a book-list CSV (ISBN or folded title + author)",
    )
    d.add_argument("file", nargs="?", help="CSV path; reads stdin when omitted or given as -")
    d.add_argument("--isbn", metavar="COL", help="ISBN column (default: autodetect isbn / ISBN-13 / …)")
    d.add_argument("--title", metavar="COL", help="title column (default: autodetect title / 書名 / …)")
    d.add_argument("--author", metavar="COL", help="author column (default: autodetect author / 著者 / …)")
    d.add_argument("--json", action="store_true", help="structured JSON of duplicate groups")
    d.add_argument("--all", action="store_true", help="with --json, include singleton groups too")
    d.add_argument("--unique", nargs="?", const="-", metavar="FILE",
                   help="write unique rows (first spelling wins) to FILE, or stdout when FLAG only")
    d.add_argument("-o", "--output", metavar="FILE", help="write unique rows to FILE (implies --unique)")



    a = p.parse_args(argv)
    if a.cmd == "fold":
        return _cmd_fold(a)
    if a.cmd == "isbn":
        return _cmd_isbn(a)
    if a.cmd == "lookup":
        return _cmd_lookup(a)
    if a.cmd == "dedupe":
        return _cmd_dedupe(a)
    return 2


if __name__ == "__main__":
    sys.exit(main())
