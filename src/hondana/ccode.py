"""Decode the Japanese C-code (分類記号, part of the 日本図書コード).

A C-code is ``C`` plus four digits printed next to the ISBN on Japanese
books: 1st digit 販売対象 (audience), 2nd 発行形態 (form), 3rd 内容 major
class and 4th 内容 minor class. The labels below follow the
「分類記号（C コード）一覧表」 in the Japan ISBN Agency's
「ISBN および日本図書コード・書籍JANコード 利用の手引き 2025年版」 (p. 24,
https://isbn.jpo.or.jp/doc/ISBN_jp2025.pdf). Blank cells in that table are
reserved codes; they decode with an empty ``detail``.

The C-code is chosen by the publisher as a shelving hint, so it is not a
library classification (use ``Book.ndc`` for that).
"""
from __future__ import annotations

from typing import NamedTuple, Optional

__all__ = ["CCode", "decode_ccode"]

#: 1st digit — 販売対象
AUDIENCE = {
    "0": "一般",
    "1": "教養",
    "2": "実用",
    "3": "専門",
    "4": "検定教科書・消費税非課税品",
    "5": "女性",
    "6": "学参I（小中学生対象）",
    "7": "学参II（高校生対象）",
    "8": "児童（中学生以下対象）",
    "9": "雑誌扱いコミックスおよびムック",
}

#: 2nd digit — 発行形態
FORM = {
    "0": "単行本",
    "1": "文庫",
    "2": "新書",
    "3": "全集・双書",
    "4": "ムック・その他",
    "5": "辞典・事典",
    "6": "図鑑",
    "7": "絵本",
    "8": "電磁的記録媒体など",
    "9": "コミックス",
}

#: 3rd digit — 内容 (大分類)
SUBJECT = {
    "0": "総記",
    "1": "哲学・心理学・宗教",
    "2": "歴史・地理",
    "3": "社会科学",
    "4": "自然科学",
    "5": "工学・工業",
    "6": "産業",
    "7": "芸術・生活",
    "8": "語学",
    "9": "文学",
}

#: 3rd + 4th digits — 内容 (中分類); codes not listed are reserved.
DETAIL = {
    "00": "総記", "01": "百科事典", "02": "年鑑・雑誌", "04": "情報科学",
    "10": "哲学", "11": "心理（学）", "12": "倫理（学）", "14": "宗教", "15": "仏教",
    "16": "キリスト教",
    "20": "歴史総記", "21": "日本歴史", "22": "外国歴史", "23": "伝記・系譜", "25": "地理",
    "26": "旅行",
    "30": "社会科学総記", "31": "政治（含む国防・軍事）", "32": "法律", "33": "経済・財政・統計",
    "34": "経営", "36": "社会", "37": "教育", "39": "民族・風習",
    "40": "自然科学総記", "41": "数学", "42": "物理学", "43": "化学", "44": "天文・地学",
    "45": "生物学", "47": "医学・歯学・薬学",
    "50": "工学・工業総記", "51": "土木", "52": "建築", "53": "機械", "54": "電気",
    "55": "電子通信", "56": "海事・兵器", "57": "採鉱・冶金", "58": "各種工業",
    "60": "産業総記", "61": "農林業", "62": "水産業", "63": "商業", "65": "交通・通信",
    "70": "芸術総記", "71": "絵画・彫刻", "72": "写真・工芸", "73": "音楽・舞踊",
    "74": "演劇・映画", "75": "体育・スポーツ", "76": "諸芸・娯楽", "77": "家事", "78": "生活",
    "79": "コミック・劇画",
    "80": "語学総記", "81": "日本語", "82": "英米語", "84": "ドイツ語", "85": "フランス語",
    "87": "各国語",
    "90": "文学総記", "91": "日本文学総記", "92": "日本文学詩歌", "93": "日本文学、小説・物語",
    "95": "日本文学、評論・随筆・その他", "97": "外国文学小説", "98": "外国文学、その他",
}

_FULLWIDTH = str.maketrans("０１２３４５６７８９Ｃｃ", "0123456789Cc")


class CCode(NamedTuple):
    """A decoded C-code. ``detail`` is ``""`` for reserved 内容 codes."""

    code: str
    audience: str
    form: str
    subject: str
    detail: str


def decode_ccode(raw: Optional[str]) -> Optional[CCode]:
    """Decode a C-code such as ``"C0093"``, ``"0093"`` or ``"Ｃ３０５５"``.

    Returns ``None`` unless the input is four digits (an optional leading
    ``C`` and surrounding spaces are ignored).

    >>> decode_ccode("C0093")
    CCode(code='0093', audience='一般', form='単行本', subject='文学', detail='日本文学、小説・物語')
    >>> decode_ccode("3055").detail
    '電子通信'
    >>> decode_ccode("0103").detail     # reserved 内容 code
    ''
    >>> decode_ccode("C12") is None
    True
    """
    s = (raw or "").strip().translate(_FULLWIDTH)
    if s[:1] in ("C", "c"):
        s = s[1:]
    if len(s) != 4 or not s.isascii() or not s.isdigit():
        return None
    return CCode(s, AUDIENCE[s[0]], FORM[s[1]], SUBJECT[s[2]], DETAIL.get(s[2:], ""))
