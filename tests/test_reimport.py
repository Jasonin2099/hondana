"""Reading back hondana's own BibTeX / RIS / CSL-JSON exports (no network)."""
import json

import pytest

from hondana import Book, dumps, from_bibtex, from_csl, from_ris, loads
from hondana.__main__ import main
from hondana.reimport import sniff

NEKO = Book(
    isbn="9784003101018",
    title="吾輩は猫である",
    author="夏目漱石／著",
    publisher="岩波書店",
    year="1990",
    source="openBD",
)
WESTERN = Book(
    isbn="9780140449136",
    title="Crime and Punishment",
    author="Dostoyevsky, Fyodor and McDuff, David",
    publisher="Penguin",
    year="2003",
)
SPECIAL = Book(isbn="", title=r"Costs $50 & 100% {off}_now \ ~ ^ #1", author="森鷗外、夏目漱石", year="1911年")
BOOKS = [NEKO, WESTERN, SPECIAL]


@pytest.mark.parametrize("fmt", ["bibtex", "ris", "csl"])
def test_round_trip_is_stable(fmt):
    text = dumps(BOOKS, fmt)
    back = loads(text)
    assert len(back) == 3
    assert all(b.source == fmt for b in back)
    # Exporting what we read gives the same text again.
    assert dumps(back, fmt) == text


@pytest.mark.parametrize("fmt", ["bibtex", "ris", "csl"])
def test_round_trip_fields(fmt):
    neko, western, special = loads(dumps(BOOKS, fmt), fmt)
    assert neko.isbn == "9784003101018"  # hyphenated on export, digits again
    assert neko.title == "吾輩は猫である"
    assert neko.author == "夏目漱石"  # role word was dropped on export
    assert neko.publisher == "岩波書店"
    assert neko.year == "1990"
    assert western.author == "Dostoyevsky, Fyodor; McDuff, David"
    assert western.isbn == "9780140449136"
    assert special.title == SPECIAL.title
    assert special.author == "森鷗外; 夏目漱石"
    assert special.year == "1911"
    assert special.isbn == ""


def test_single_book_csl_object():
    back = loads(dumps(NEKO, "csl"))
    assert [b.title for b in back] == ["吾輩は猫である"]


def test_bibtex_subset():
    text = """
% a comment line
@comment{ignored, title = {no}}
@string{pub = "Iwanami"}
@Book{key1,
  title = "{NHK} {\\&} the {{Nested}} title",
  author = {Natsume, Soseki and   Mori, Ogai},
  year = 1990,
  ISBN = {4-00-310101-4},
  note = {出典：example, {braces} ok},
}
@article(key2, title = {Paren entry}, date = {2001-04-01})
"""
    a, b = from_bibtex(text)
    assert a.title == "NHK & the Nested title"
    assert a.author == "Natsume, Soseki; Mori, Ogai"
    assert a.year == "1990"
    assert a.isbn == "9784003101018"  # ISBN-10 → 13 digits
    assert a.attribution == "出典：example, braces ok"  # note is the credit line
    assert b.title == "Paren entry" and b.year == "2001"


def test_bibtex_unterminated_raises():
    with pytest.raises(ValueError):
        from_bibtex("@book{x, title = {open")


def test_ris_subset():
    text = "\ufeffTY  - BOOK\r\nT1  - 坊っちゃん\r\nA1  - 夏目漱石\r\nY1  - 1989/05/16/\r\nSN  - 9784101010038 4101010030\r\nN1  - 出典：例\r\nN1  - License: cc0\r\nER  - \r\n"
    (b,) = from_ris(text)
    assert b.title == "坊っちゃん"
    assert b.author == "夏目漱石"
    assert b.year == "1989"
    assert b.isbn == "9784101010038"
    assert b.attribution == "出典：例"
    assert b.licence == "cc0"  # American "License:" is accepted
    # Lines outside a record and a record without ER are ignored.
    assert from_ris("TI  - stray\nTY  - BOOK\nTI  - unfinished\n") == []


def test_csl_variants():
    data = [
        {"type": "book", "title": "A", "author": [{"family": "夏目", "given": "漱石"}, {"literal": "森鷗外"}, {"family": "Only"}],
         "issued": {"raw": "2004-05"}, "ISBN": "not an isbn"},
        {"title": "B", "issued": {"literal": "c. 1999"}},
    ]
    a, b = from_csl(data)
    assert a.author == "夏目, 漱石; 森鷗外; Only"
    assert a.year == "2004"
    assert a.isbn == "not an isbn"  # kept as written when it doesn't check out
    assert b.year == "1999"
    assert from_csl(json.dumps(data))[0].title == "A"
    with pytest.raises(ValueError):
        from_csl(["not an object"])


def test_sniff():
    assert sniff("  [ ]") == "csl"
    assert sniff("{}") == "csl"
    assert sniff("% x\n@book{a,\n}") == "bibtex"
    assert sniff("TY  - BOOK\nN1  - mail me @misc{x}\nER  - ") == "ris"
    with pytest.raises(ValueError):
        sniff("title,author\n")
    with pytest.raises(ValueError):
        loads("[]", "endnote")


def test_cli_convert_ris_to_bibtex(tmp_path, capsys):
    src = tmp_path / "list.ris"
    src.write_text(dumps([NEKO, WESTERN], "ris"), encoding="utf-8")
    assert main(["convert", str(src), "--to", "bibtex"]) == 0
    assert capsys.readouterr().out == dumps(loads(src.read_text(encoding="utf-8")), "bibtex")


def test_cli_convert_stdin_json(monkeypatch, capsys):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(dumps(NEKO, "bibtex")))
    assert main(["convert", "--from", "bibtex"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["title"] == "吾輩は猫である"
    assert out[0]["source"] == "bibtex"


def test_cli_convert_errors(monkeypatch, capsys):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("title,author\n"))
    assert main(["convert"]) == 1
    assert "cannot read input" in capsys.readouterr().err
    monkeypatch.setattr("sys.stdin", io.StringIO("[]"))
    assert main(["convert"]) == 1
    assert "no records" in capsys.readouterr().err


CREDIT = Book(
    isbn="9784634342507",
    title="海の道と東西の出会い",
    author="青木康征／著",
    year="1998",
    source="Japan Search",
    licence="cc-by",
    attribution="出典：ジャパンサーチ「全国書誌（国立国会図書館）」のメタデータ（https://jpsearch.go.jp/database/natbib）",
)


@pytest.mark.parametrize("fmt", ["bibtex", "ris", "csl"])
def test_round_trip_keeps_licence_and_attribution(fmt):
    text = dumps(CREDIT, fmt)
    back = loads(text)
    assert len(back) == 1
    assert back[0].licence == "cc-by"
    assert back[0].attribution == CREDIT.attribution
    assert dumps(back, fmt) == text


@pytest.mark.parametrize("fmt", ["bibtex", "ris", "csl"])
def test_round_trip_mixed_with_and_without_credits(fmt):
    text = dumps([NEKO, CREDIT, WESTERN], fmt)
    back = loads(text)
    assert [b.licence for b in back] == ["", "cc-by", ""]
    assert [b.attribution for b in back] == ["", CREDIT.attribution, ""]
    assert dumps(back, fmt) == text


def test_cli_convert_preserves_credits(tmp_path, capsys):
    src = tmp_path / "list.bib"
    src.write_text(dumps(CREDIT, "bibtex"), encoding="utf-8")
    assert main(["convert", str(src), "--to", "ris"]) == 0
    out = capsys.readouterr().out
    assert out == dumps(loads(src.read_text(encoding="utf-8")), "ris")
    assert "N1  - 出典：ジャパンサーチ" in out
    assert "N1  - Licence: cc-by" in out
