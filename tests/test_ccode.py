import json

from hondana import Book, CCode, decode_ccode
from hondana.__main__ import main
from hondana.ccode import AUDIENCE, DETAIL, FORM, SUBJECT


def test_decode_examples():
    assert decode_ccode("C0093") == CCode("0093", "一般", "単行本", "文学", "日本文学、小説・物語")
    assert decode_ccode("3055") == CCode("3055", "専門", "単行本", "工学・工業", "電子通信")
    assert decode_ccode("1036").detail == "社会"
    assert decode_ccode("8797").audience == "児童（中学生以下対象）"
    assert decode_ccode("0179").form == "文庫"
    assert decode_ccode("0179").detail == "コミック・劇画"


def test_decode_accepts_prefix_and_full_width():
    assert decode_ccode(" c0093 ") == decode_ccode("0093")
    assert decode_ccode("Ｃ００９３") == decode_ccode("0093")


def test_decode_rejects_bad_input():
    for raw in (None, "", "C", "C12", "C00933", "00a3", "C-0093", "٠٠٩٣"):
        assert decode_ccode(raw) is None, raw


def test_reserved_detail_is_empty():
    info = decode_ccode("0003")  # 03 is a blank (reserved) cell in the official table
    assert info is not None and info.subject == "総記" and info.detail == ""


def test_tables_are_complete():
    digits = set("0123456789")
    assert set(AUDIENCE) == set(FORM) == set(SUBJECT) == digits
    assert all(len(k) == 2 and k[0] in digits and k[1] in digits for k in DETAIL)
    # 68 assigned 内容 codes in the 2025 table; every major class has its 総記 (x0)
    assert len(DETAIL) == 68
    assert all(f"{d}0" in DETAIL for d in digits)


def test_book_ccode_info_and_to_dict():
    b = Book("9784003101018", "吾輩は猫である", ccode="0193")
    assert b.ccode_info == CCode("0193", "一般", "文庫", "文学", "日本文学、小説・物語")
    d = b.to_dict()
    assert d["ccode"] == "0193"
    assert d["ccode_labels"] == {
        "audience": "一般", "form": "文庫", "subject": "文学", "detail": "日本文学、小説・物語",
    }
    plain = Book("9784003101018", "吾輩は猫である")
    assert plain.ccode_info is None and "ccode_labels" not in plain.to_dict()


def test_cli_ccode(capsys):
    assert main(["ccode", "C0093", "3055"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "C0093\t一般\t単行本\t文学\t日本文学、小説・物語",
        "C3055\t専門\t単行本\t工学・工業\t電子通信",
    ]
    assert main(["ccode", "--json", "C0003"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "code": "0003", "audience": "一般", "form": "単行本", "subject": "総記", "detail": "",
    }
    assert main(["ccode", "C12"]) == 1
    assert "invalid C-code: C12" in capsys.readouterr().err
