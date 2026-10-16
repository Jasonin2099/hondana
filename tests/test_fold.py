import pytest
from hondana import fold, kata_to_hira, hira_to_kata, to_shinjitai, strip_reading_lines


@pytest.mark.parametrize("a,b", [
    ("圖書館", "図書館"), ("图书馆", "図書館"), ("國學", "国学"), ("讀書", "读书"),
    ("ハリー・ポッター", "はりーぽったー"), ("ﾊﾘｰ ﾎﾟｯﾀｰ", "ハリーポッター"),
    ("ＡＢＣ　入門", "abc入門"), ("『吾輩は猫である』", "吾輩は猫である"),
    ("經濟學", "経済学"),
])
def test_equal(a, b):
    assert fold(a) == fold(b)


@pytest.mark.parametrize("a,b", [
    ("机", "機"),   # desk is not machine
    ("上巻", "下巻"),
    ("1", "2"),
])
def test_not_equal(a, b):
    assert fold(a) != fold(b)


def test_kana_roundtrip():
    assert kata_to_hira("カタカナヶ") == "かたかなゖ"
    assert hira_to_kata("ひらがな") == "ヒラガナ"


def test_switches():
    assert fold("ハリー", kana=False) == "ハリ"
    assert fold("ハリー", long_vowel=False) == "はりー"
    assert fold("圖", han=False) == "圖"
    assert to_shinjitai("书", simplified=False) == "书"
    assert to_shinjitai("書", kyujitai=False) == "書"


def test_empty():
    assert fold("") == "" and fold(None) == ""


def test_reading_lines():
    assert strip_reading_lines("吾輩は猫である\nワガハイ ワ ネコ デ アル") == "吾輩は猫である"
    assert strip_reading_lines("A\n副題あり") == "A\n副題あり"
