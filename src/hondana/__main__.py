"""python -m hondana fold|isbn|ccode|ndc|lookup|search|dedupe|convert …

  fold   — print the matching key for some text
  isbn   — find, validate and hyphenate ISBNs in text (no network)
  ccode  — decode Japanese C-codes into 販売対象 / 発行形態 / 内容 (no network)
  ndc    — label NDC marks with their main class, 0 総記 … 9 文学 (no network)
  lookup — look ISBNs up across openBD / NDL / Google Books / Open Library
  search — search by title or author (NDL Search, Open Library)
  dedupe — report (or drop) duplicate rows in a book-list CSV
  convert — read back BibTeX / RIS / CSL-JSON that hondana wrote (no network)
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional, Sequence

from .ccode import decode_ccode
from .ndc import ndc_class
from .isbn import find_isbns, hyphenate, is_valid, registration_group, to_isbn13
from .export import dumps
from .reimport import loads
from .lookup import Book
from .dedupe import _AUTHOR_ALIASES, _ISBN_ALIASES, _TITLE_ALIASES, dedupe, resolve_field
from . import fold, fold_steps, lookup_many, search


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
        prefix, name = registration_group(text) or ("", "")
        if a.json:
            print(json.dumps(
                {"isbn": text, "isbn13": isbn13, "hyphenated": hyp, "valid": valid,
                 "group": prefix, "group_name": name},
                ensure_ascii=False,
            ))
        elif a.validate:
            print("ok" if valid else "invalid")
        else:
            if not valid:
                print("invalid", file=sys.stderr)
                return 1
            print(f"{hyp or isbn13}\t{name}" if a.group else (hyp or isbn13))
        return 0 if valid else 1

    found = find_isbns(text)
    rows = []
    for i in found:
        prefix, name = registration_group(i) or ("", "")
        rows.append({"isbn13": i, "hyphenated": hyphenate(i) or i, "valid": True,
                     "group": prefix, "group_name": name})
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
            print(f"{r['hyphenated']}\t{r['group_name']}" if a.group else r["hyphenated"])
    return 0 if rows else 1


def _cmd_ccode(a: argparse.Namespace) -> int:
    codes = list(a.code) or _read_text(()).split()
    if not codes:
        print("no C-code given", file=sys.stderr)
        return 1
    rows = []
    bad = 0
    for raw in codes:
        info = decode_ccode(raw)
        if info is None:
            print(f"invalid C-code: {raw}", file=sys.stderr)
            bad += 1
            continue
        rows.append(info)
    if a.json:
        payload = [r._asdict() for r in rows]
        print(json.dumps(payload[0] if len(codes) == 1 and payload else payload,
                         ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print("\t".join(("C" + r.code, r.audience, r.form, r.subject, r.detail or "-")))
    return 1 if bad else 0


def _cmd_ndc(a: argparse.Namespace) -> int:
    marks = list(a.mark) or _read_text(()).split()
    if not marks:
        print("no NDC mark given", file=sys.stderr)
        return 1
    rows = []
    bad = 0
    for raw in marks:
        info = ndc_class(raw)
        if info is None:
            print(f"invalid NDC mark: {raw}", file=sys.stderr)
            bad += 1
            continue
        rows.append(info)
    if a.json:
        payload = [r._asdict() for r in rows]
        print(json.dumps(payload[0] if len(marks) == 1 and payload else payload,
                         ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print("\t".join((r.code, r.main, r.label, r.label_en)))
    return 1 if bad else 0


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


def _cmd_search(a: argparse.Namespace) -> int:
    query = " ".join(a.query) if a.query else ""
    title, author = a.title or "", a.author or ""
    if not query and not title and not author:
        query = _read_text(()).strip()
    if not query and not title and not author:
        print("no query given", file=sys.stderr)
        return 1
    try:
        books = search(
            query,
            title=title,
            author=author,
            limit=a.limit,
            on_error=lambda n, e: print(f"# {n}: {type(e).__name__}", file=sys.stderr),
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    fmt = a.format or ("json" if len(books) == 1 else "table")
    if not books:
        print("no results", file=sys.stderr)
        return 1
    if fmt == "json":
        print(json.dumps([b.to_dict() for b in books], ensure_ascii=False, indent=2))
    elif fmt in ("bibtex", "ris", "csl"):
        sys.stdout.write(dumps(books if len(books) > 1 else books[0], fmt))
    else:
        print(_format_table(books))
    return 0


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


def _cmd_convert(a: argparse.Namespace) -> int:
    if a.file and a.file != "-":
        with open(a.file, encoding="utf-8-sig") as fh:
            text = fh.read()
    else:
        text = sys.stdin.read()
    try:
        books = loads(text, None if a.input == "auto" else a.input)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"cannot read input: {e}", file=sys.stderr)
        return 1
    if not books:
        print("no records found", file=sys.stderr)
        return 1
    fmt = a.to
    if fmt == "json":
        print(json.dumps([b.to_dict() for b in books], ensure_ascii=False, indent=2))
    elif fmt == "table":
        print(_format_table(books))
    else:
        sys.stdout.write(dumps(books if len(books) > 1 else books[0], fmt))
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
    i.add_argument("--group", action="store_true",
                   help="also print the registration-group name (Japan, English language, …), tab-separated")
    i.add_argument("--json", action="store_true", help="structured JSON output (includes group / group_name)")

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


    c = sub.add_parser(
        "ccode",
        help="decode Japanese C-codes (販売対象 / 発行形態 / 内容), no network",
    )
    c.add_argument("code", nargs="*", help="C-codes like C0093 or 3055; reads stdin when omitted")
    c.add_argument("--json", action="store_true", help="structured JSON output")

    n = sub.add_parser(
        "ndc",
        help="label NDC marks with their main class (0 総記 … 9 文学), no network",
    )
    n.add_argument("mark", nargs="*", help="NDC marks like 913.6 or 007; reads stdin when omitted")
    n.add_argument("--json", action="store_true", help="structured JSON output")

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


    s = sub.add_parser(
        "search",
        help="search by title or author (NDL Search, Open Library)",
    )
    s.add_argument("query", nargs="*", help="free-text query; reads stdin when omitted")
    s.add_argument("--title", default="", help="search this title")
    s.add_argument("--author", default="", help="search this author / creator")
    s.add_argument("--limit", type=int, default=10, metavar="N", help="maximum hits (default 10)")
    s.add_argument(
        "--format", choices=("json", "table", "bibtex", "ris", "csl"), default=None,
        help="output format (default: json for one hit, table for many)",
    )

    v = sub.add_parser(
        "convert",
        help="read BibTeX / RIS / CSL-JSON that hondana wrote and print it in another format",
    )
    v.add_argument("file", nargs="?", help="input file; reads stdin when omitted or given as -")
    v.add_argument("--from", dest="input", choices=("auto", "bibtex", "ris", "csl"), default="auto",
                   help="input format (default: guess from the content)")
    v.add_argument("--to", choices=("json", "table", "bibtex", "ris", "csl"), default="json",
                   help="output format (default: json, one Book per record)")

    a = p.parse_args(argv)
    if a.cmd == "fold":
        return _cmd_fold(a)
    if a.cmd == "isbn":
        return _cmd_isbn(a)
    if a.cmd == "ccode":
        return _cmd_ccode(a)
    if a.cmd == "ndc":
        return _cmd_ndc(a)
    if a.cmd == "lookup":
        return _cmd_lookup(a)
    if a.cmd == "search":
        return _cmd_search(a)
    if a.cmd == "dedupe":
        return _cmd_dedupe(a)
    if a.cmd == "convert":
        return _cmd_convert(a)
    return 2


if __name__ == "__main__":
    sys.exit(main())
