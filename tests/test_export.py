"""Bibliography export: BibTeX, RIS, CSL-JSON (no network)."""
import json

import pytest

from hondana import Book, dumps, to_bibtex, to_csl, to_ris
from hondana.export import citation_key, split_authors


NEKO = Book(
    isbn="9784003101018",
    title="吾輩は猫である",
    author="夏目漱石／著",
    publisher="岩波書店",
    year="1990",
    source="openBD",
)

WESTERN = Book(
    isbn="978-0-14-044913-6",
    title="Crime and Punishment",
    author="Dostoyevsky, Fyodor and McDuff, David",
    publisher="Penguin",
    year="2003",
)


def test_split_authors_drops_roles_and_splits():
    assert split_authors("夏目漱石／著") == ["夏目漱石"]
    assert split_authors("森鷗外、夏目漱石") == ["森鷗外", "夏目漱石"]
    assert split_authors("Dostoyevsky, Fyodor and McDuff, David") == [
        "Dostoyevsky, Fyodor",
        "McDuff, David",
    ]
    assert split_authors("") == []
    assert split_authors("  夏目漱石著  ") == ["夏目漱石"]


def test_citation_key_uses_isbn_digits():
    assert citation_key(NEKO) == "isbn9784003101018"
    assert citation_key(WESTERN) == "isbn9780140449136"
    assert citation_key(Book(isbn="", title="Hello!")).startswith("Hello")


def test_to_bibtex_japanese():
    text = to_bibtex(NEKO)
    assert text.startswith("@book{isbn9784003101018,")
    assert "title = {吾輩は猫である}" in text
    assert "author = {夏目漱石}" in text
    assert "publisher = {岩波書店}" in text
    assert "year = {1990}" in text
    assert "isbn = {978-4-00-310101-8}" in text
    assert text.endswith("}\n")
    # Same via the Book method
    assert NEKO.to_bibtex() == text


def test_to_bibtex_escapes_latex_specials():
    b = Book(isbn="9784003101018", title=r"Costs $50 & 100% {off}_now")
    text = to_bibtex(b)
    assert r"Costs \$50 \& 100\% \{off\}\_now" in text
    assert " & " not in text and " 100%" not in text


def test_to_bibtex_omits_empty_fields():
    text = to_bibtex(Book(isbn="9784003101018", title="Only Title"))
    assert "title = {Only Title}" in text
    assert "author" not in text
    assert "publisher" not in text
    assert "year" not in text
    assert "isbn = {978-4-00-310101-8}" in text


def test_to_ris():
    text = to_ris(NEKO)
    assert text == (
        "TY  - BOOK\n"
        "TI  - 吾輩は猫である\n"
        "AU  - 夏目漱石\n"
        "PB  - 岩波書店\n"
        "PY  - 1990\n"
        "SN  - 978-4-00-310101-8\n"
        "ER  - \n"
    )
    assert NEKO.to_ris() == text


def test_to_ris_multiple_authors():
    lines = to_ris(WESTERN).splitlines()
    assert "AU  - Dostoyevsky, Fyodor" in lines
    assert "AU  - McDuff, David" in lines
    assert "SN  - 978-0-14-044913-6" in lines


def test_to_csl_japanese_uses_literal_name():
    item = to_csl(NEKO)
    assert item == {
        "id": "isbn9784003101018",
        "type": "book",
        "title": "吾輩は猫である",
        "author": [{"literal": "夏目漱石"}],
        "publisher": "岩波書店",
        "issued": {"date-parts": [[1990]]},
        "ISBN": "978-4-00-310101-8",
    }
    assert NEKO.to_csl() == item


def test_to_csl_western_splits_family_given():
    item = to_csl(WESTERN)
    assert item["author"] == [
        {"family": "Dostoyevsky", "given": "Fyodor"},
        {"family": "McDuff", "given": "David"},
    ]


def test_dumps_one_and_many():
    bib = dumps(NEKO, "bibtex")
    assert bib == to_bibtex(NEKO)
    two = dumps([NEKO, WESTERN], "bibtex")
    assert two == to_bibtex(NEKO) + to_bibtex(WESTERN)

    ris = dumps([NEKO, WESTERN], "ris")
    assert ris == to_ris(NEKO) + "\n" + to_ris(WESTERN)

    one = json.loads(dumps(NEKO, "csl"))
    assert one["id"] == "isbn9784003101018" and one["type"] == "book"
    many = json.loads(dumps([NEKO, WESTERN], "csl"))
    assert isinstance(many, list) and len(many) == 2


def test_dumps_rejects_unknown_format():
    with pytest.raises(ValueError, match="unknown format"):
        dumps(NEKO, "endnote")


def test_cli_lookup_format_bibtex_ris_csl(monkeypatch, capsys):
    import hondana.__main__ as cli

    monkeypatch.setattr(cli, "lookup_many", lambda isbns, **kw: [NEKO])
    assert cli.main(["lookup", "--format", "bibtex", "9784003101018"]) == 0
    assert capsys.readouterr().out == to_bibtex(NEKO)

    assert cli.main(["lookup", "--format", "ris", "9784003101018"]) == 0
    assert capsys.readouterr().out == to_ris(NEKO)

    assert cli.main(["lookup", "--format", "csl", "9784003101018"]) == 0
    assert json.loads(capsys.readouterr().out) == to_csl(NEKO)


def test_cli_lookup_format_csl_many_is_array(monkeypatch, capsys):
    import hondana.__main__ as cli

    monkeypatch.setattr(cli, "lookup_many", lambda isbns, **kw: [NEKO, WESTERN])
    assert cli.main(["lookup", "--format", "csl", "9784003101018", "9780140449136"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list) and [i["id"] for i in payload] == [
        "isbn9784003101018",
        "isbn9780140449136",
    ]
