"""Tests for hondana.dedupe (no network)."""
import csv
import io
from hondana import dedupe, dedupe_key
from hondana.__main__ import main


def _rows(*lines: str):
    text = "title,author,isbn\n" + "\n".join(lines) + "\n"
    return list(csv.DictReader(io.StringIO(text)))


def test_dedupe_by_isbn_and_folded_text():
    rows = _rows(
        "吾輩は猫である,夏目漱石,4-00-310101-4",
        "吾輩ハ猫デアル,夏目 漱石,9784003101018",
        "ﾊﾘｰ･ﾎﾟｯﾀｰと賢者の石,J.K.ローリング,",
        "ハリー・ポッターと賢者の石,J. K. ローリング,",
        "「坊っちゃん」,夏目漱石,",
    )
    result = dedupe(rows)
    assert [r["title"] for r in result.unique] == [
        "吾輩は猫である",
        "ﾊﾘｰ･ﾎﾟｯﾀｰと賢者の石",
        "「坊っちゃん」",
    ]
    assert result.extra == 2
    assert len(result.duplicate_groups) == 2
    neko = result.duplicate_groups[0]
    assert neko.kind == "isbn" and neko.isbn == "9784003101018"
    assert len(neko.rows) == 2


def test_dedupe_bridges_isbn_and_text():
    # First row has the ISBN, third has the same title+author without one.
    rows = _rows(
        "吾輩は猫である,夏目漱石,9784003101018",
        "坊っちゃん,夏目漱石,",
        "吾輩ハ猫デアル,夏目 漱石,",
    )
    result = dedupe(rows)
    assert len(result) == 2
    group = result.groups[0]
    assert group.kind == "isbn" and len(group.rows) == 2
    assert [r["title"] for r in group.rows] == ["吾輩は猫である", "吾輩ハ猫デアル"]


def test_bad_isbn_does_not_merge_different_books():
    # Wrong check digit is ignored; rows fall back to title+author.
    rows = _rows(
        "吾輩は猫である,夏目漱石,9784003101019",
        "坊っちゃん,夏目漱石,9784003101019",
    )
    result = dedupe(rows)
    assert len(result) == 2
    assert result.extra == 0


def test_blank_rows_stay_separate():
    rows = _rows(",,", ",,")
    result = dedupe(rows)
    assert len(result) == 2 and result.extra == 0


def test_dedupe_key_isbn_vs_text():
    assert dedupe_key({"isbn": "4-00-310101-4", "title": "x", "author": "y"}) == (
        "isbn",
        "9784003101018",
    )
    assert dedupe_key({"isbn": "", "title": "圖書館", "author": "某"}) == dedupe_key(
        {"isbn": "", "title": "図書館", "author": "某"}
    )


def test_alias_columns_autodetect():
    text = "書名,著者,ISBN\n圖書館戦争,有川浩,9784043898030\n図書館戦争,有川 浩,\n"
    # 9784043898030 may be invalid — use a valid one.
    from hondana import to_isbn13
    # just use the neko isbn
    text = "書名,著者,ISBN\n吾輩は猫である,夏目漱石,9784003101018\n図書館,有川浩,\n"
    rows = list(csv.DictReader(io.StringIO(text)))
    result = dedupe(rows)
    assert result.groups[0].isbn == "9784003101018"
    assert result.groups[1].kind == "text"


def test_cli_reports_groups(tmp_path, capsys):
    p = tmp_path / "books.csv"
    p.write_text(
        "title,author,isbn\n"
        "吾輩は猫である,夏目漱石,4-00-310101-4\n"
        "吾輩ハ猫デアル,夏目 漱石,9784003101018\n"
        "坊っちゃん,夏目漱石,\n",
        encoding="utf-8",
    )
    assert main(["dedupe", str(p)]) == 0
    out = capsys.readouterr().out
    assert "group 1 (isbn 9784003101018), 2 rows" in out
    assert "2 unique, 1 duplicate groups (1 extra rows)" in out


def test_cli_unique_and_json(tmp_path, capsys):
    import json
    src = tmp_path / "books.csv"
    src.write_text(
        "title,author,isbn\n"
        "吾輩は猫である,夏目漱石,9784003101018\n"
        "吾輩ハ猫デアル,夏目 漱石,\n",
        encoding="utf-8",
    )
    dest = tmp_path / "clean.csv"
    assert main(["dedupe", str(src), "-o", str(dest)]) == 0
    cleaned = dest.read_text(encoding="utf-8")
    assert "吾輩は猫である" in cleaned and "吾輩ハ猫デアル" not in cleaned
    assert main(["dedupe", str(src), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["unique"] == 1 and payload["extra"] == 1
    assert payload["groups"][0]["kind"] == "isbn"


def test_cli_no_duplicates(tmp_path, capsys):
    p = tmp_path / "one.csv"
    p.write_text("title,author,isbn\n坊っちゃん,夏目漱石,\n", encoding="utf-8")
    assert main(["dedupe", str(p)]) == 0
    assert capsys.readouterr().out.strip() == "1 rows, no duplicates"


def test_cli_stdin(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("title,author,isbn\nA,B,\nA,B,\n"),
    )
    assert main(["dedupe"]) == 0
    assert "1 unique, 1 duplicate groups" in capsys.readouterr().out
