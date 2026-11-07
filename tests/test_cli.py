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
