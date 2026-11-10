"""Smoke tests for the hondana CLI (no network)."""
import json
from hondana.__main__ import main


def test_isbn_hyphenate_bare(capsys):
    assert main(["isbn", "9784003101018"]) == 0
    assert capsys.readouterr().out.strip() == "978-4-00-310101-8"


def test_isbn_validate_ok_and_bad(capsys):
    assert main(["isbn", "--validate", "9784003101018"]) == 0
    assert capsys.readouterr().out.strip() == "ok"
    assert main(["isbn", "--validate", "123"]) == 1
    assert capsys.readouterr().out.strip() == "invalid"


def test_isbn_find_in_text(capsys):
    assert main(["isbn", "see ISBN 978-4-00-310101-8 and also 4003101014 here"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == ["978-4-00-310101-8"]


def test_isbn_json(capsys):
    assert main(["isbn", "--json", "4-00-310101-4"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["valid"] and d["hyphenated"] == "978-4-00-310101-8"


def test_fold_still_works(capsys):
    assert main(["fold", "ＡＢＣ"]) == 0
    assert "abc" in capsys.readouterr().out.lower()


def test_lookup_reads_stdin_and_passes_rate(monkeypatch, capsys):
    import io
    import hondana.__main__ as cli
    from hondana import Book
    seen = {}

    def fake_many(isbns, **kw):
        seen["isbns"], seen["rate"] = list(isbns), kw["rate"]
        return [Book(i, "t", source="x") for i in seen["isbns"]]

    monkeypatch.setattr(cli, "lookup_many", fake_many)
    monkeypatch.setattr("sys.stdin", io.StringIO("978-4-00-310101-8\n978-0-14-044913-6\n"))
    assert cli.main(["lookup", "--rate", "1.5", "--format", "json"]) == 0
    assert seen == {"isbns": ["978-4-00-310101-8", "978-0-14-044913-6"], "rate": 1.5}
    assert "978-4-00-310101-8" in capsys.readouterr().out


def test_lookup_default_rate(monkeypatch):
    import hondana.__main__ as cli
    from hondana import Book
    rates = []
    monkeypatch.setattr(cli, "lookup_many", lambda isbns, **kw: rates.append(kw["rate"]) or [Book("9784003101018", "t")])
    cli.main(["lookup", "9784003101018"])
    assert rates == [0.5]


def test_lookup_no_input(monkeypatch, capsys):
    import io
    import hondana.__main__ as cli
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert cli.main(["lookup"]) == 1
