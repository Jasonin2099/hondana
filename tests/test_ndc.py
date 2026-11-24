import json

from hondana import Book, NdcClass, ndc_class
from hondana.__main__ import main
from hondana.ndc import NDC_MAIN_CLASSES


def test_main_classes_only():
    # Only the ten one-digit main classes are bundled (the full schedules are
    # copyrighted by the Japan Library Association).
    assert list(NDC_MAIN_CLASSES) == list("0123456789")
    assert [v[0] for v in NDC_MAIN_CLASSES.values()] == [
        "総記", "哲学", "歴史", "社会科学", "自然科学", "技術", "産業", "芸術", "言語", "文学",
    ]


def test_examples():
    assert ndc_class("913.6") == NdcClass("913.6", "9", "文学", "Literature")
    assert ndc_class("007.64") == NdcClass("007.64", "0", "総記", "General works")
    assert ndc_class("2") == NdcClass("2", "2", "歴史", "History")
    assert ndc_class("49").label == "自然科学"
    assert ndc_class("548.3").label_en == "Technology"


def test_prefixes_spaces_and_full_width():
    for raw in ("NDC10:913.6", "ndc9 913.6", "NDC 913.6", "NDC: 913.6", " 913.6 ", "９１３．６", "ＮＤＣ１０：９１３．６"):
        assert ndc_class(raw) == ndc_class("913.6"), raw


def test_rejects_other_input():
    for raw in (None, "", ".6", "9136", "913.", "913.6.1", "K913", "E", "913-914", "913/N", "NDC10", "NDC913.6", "٩١٣"):
        assert ndc_class(raw) is None, raw


def test_book_ndc_info_and_to_dict():
    b = Book("9784003101018", "吾輩は猫である", ndc="913.6")
    assert b.ndc_info == NdcClass("913.6", "9", "文学", "Literature")
    d = b.to_dict()
    assert d["ndc"] == "913.6"
    assert d["ndc_class"] == {"main": "9", "label": "文学", "label_en": "Literature"}
    plain = Book("9784003101018", "吾輩は猫である")
    assert plain.ndc_info is None and "ndc_class" not in plain.to_dict()
    odd = Book("9784003101018", "吾輩は猫である", ndc="K913")
    assert odd.ndc_info is None and "ndc_class" not in odd.to_dict()


def test_cli_ndc(capsys):
    assert main(["ndc", "913.6", "007"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "913.6\t9\t文学\tLiterature",
        "007\t0\t総記\tGeneral works",
    ]
    assert main(["ndc", "--json", "NDC10:210.1"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "code": "210.1", "main": "2", "label": "歴史", "label_en": "History",
    }
    assert main(["ndc", "913.6", "K913"]) == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["913.6\t9\t文学\tLiterature"]
    assert "invalid NDC mark: K913" in captured.err
