import pytest
from hondana import fold, kata_to_hira, hira_to_kata, to_shinjitai, strip_reading_lines, width


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


KYU_BATCH_2 = "惠恵 榮栄 衞衛 鹽塩 歐欧 穩穏 擴拡 覺覚 勸勧 卷巻 歡歓 縣県 險険 權権 顯顕 嚴厳 處処 壽寿 從従 燒焼".split()


@pytest.mark.parametrize("pair", KYU_BATCH_2)
def test_kyujitai_batch_2(pair):
    old, new = pair
    assert to_shinjitai(old) == new
    assert to_shinjitai(old, simplified=False) == new
    assert fold(old) == fold(new)


@pytest.mark.parametrize("a,b", [
    ("歐洲史", "欧洲史"), ("權利", "権利"), ("縣史", "県史"), ("全卷", "全巻"),
])
def test_kyujitai_batch_2_words(a, b):
    assert fold(a) == fold(b)


def test_kyujitai_pairs_have_no_duplicate_keys():
    from hondana._tables import _KYU
    keys = [tok[0] for tok in _KYU.split()]
    assert len(keys) == len(set(keys))


# batch 3: common in personal and place names
KYU_BATCH_3 = "濱浜 邊辺 齋斎 齊斉 瀧滝 德徳 眞真 靜静 淺浅 豐豊 繩縄 驒騨 莊荘 彌弥 稻稲 澁渋 鄕郷 藏蔵 寶宝 黑黒".split()


@pytest.mark.parametrize("pair", KYU_BATCH_3)
def test_kyujitai_batch_3_names(pair):
    old, new = pair
    assert to_shinjitai(old) == new
    assert fold(old) == fold(new)


@pytest.mark.parametrize("a,b", [
    ("濱田", "浜田"), ("渡邊", "渡辺"), ("齋藤", "斎藤"), ("飛驒", "飛騨"), ("澁谷", "渋谷"), ("黑田", "黒田"),
])
def test_kyujitai_batch_3_words(a, b):
    assert fold(a) == fold(b)


SIMP_BATCH_2 = "计計 认認 识識 诗詩 证証 乐楽 线線 纪紀 级級 红紅 绘絵 续続 统統 战戦 剧劇 场場 银銀 铁鉄 农農 岁歳".split()


@pytest.mark.parametrize("pair", SIMP_BATCH_2)
def test_simplified_batch_2(pair):
    simp, new = pair
    assert to_shinjitai(simp) == new
    assert to_shinjitai(simp, kyujitai=False) == new
    assert to_shinjitai(simp, simplified=False) == simp
    assert fold(simp) == fold(new)


@pytest.mark.parametrize("a,b", [
    ("诗集", "詩集"), ("战争与和平", "戦争与和平"), ("银河铁道之夜", "銀河鉄道之夜"), ("续编", "続編"),
])
def test_simplified_batch_2_words(a, b):
    assert fold(a) == fold(b)


def test_simplified_exclusions_are_documented_and_not_folded():
    from hondana._tables import SIMP_EXCLUDED, SIMP_TO_SHIN
    for ch, why in SIMP_EXCLUDED.items():
        assert why, ch
        assert ch not in SIMP_TO_SHIN
        assert to_shinjitai(ch) == ch


def test_simplified_pairs_have_no_duplicate_or_identity_keys():
    from hondana._tables import _SIMP
    toks = _SIMP.split()
    keys = [t[0] for t in toks]
    assert len(keys) == len(set(keys))
    assert all(len(t) == 2 and t[0] != t[1] for t in toks)


@pytest.mark.parametrize("a,b", [
    ("キャット", "キヤツト"), ("ちょっと", "ちよつと"), ("ファイル", "フアイル"),
    ("霞ヶ関", "霞ケ関"), ("ｷｬｯﾄ", "きやつと"), ("くゎし", "くわし"),
])
def test_small_kana_option_folds(a, b):
    assert fold(a, small_kana=True) == fold(b, small_kana=True)


def test_small_kana_off_by_default():
    assert fold("きって") != fold("きつて")
    assert fold("キャット") == "きゃっと"


def test_small_kana_with_kana_off_keeps_script():
    from hondana.fold import fold_small_kana
    assert fold("キャット", kana=False, small_kana=True) == "キヤツト"
    assert fold_small_kana("ぁぃぅぇぉっゃゅょゎ") == "あいうえおつやゆよわ"
    assert fold_small_kana("ABC 漢字") == "ABC 漢字"


@pytest.mark.parametrize("src,expanded,dropped", [
    ("時々", "時時", "時"), ("人々", "人人", "人"), ("いすゞ", "いすず", "いす"),
    ("こゝろ", "こころ", "ころ"), ("みすゞ", "みすず", "みす"), ("ぶゝ", "ぶふ", "ぶ"),
    ("バヽ", "バハ", "バ"), ("カヾミ", "カガミ", "カミ"), ("々頭", "頭", "頭"),
])
def test_fold_iteration_marks(src, expanded, dropped):
    from hondana.fold import fold_iteration_marks
    assert fold_iteration_marks(src) == expanded
    assert fold_iteration_marks(src, "drop") == dropped


def test_iteration_marks_in_fold():
    assert fold("時々") == "時々"  # off by default
    assert fold("時々", iteration_marks="expand") == fold("時時")
    assert fold("こゝろ", iteration_marks="expand") == fold("こころ")
    assert fold("佐々木", iteration_marks="drop") == fold("佐木")


def test_iteration_marks_bad_mode():
    from hondana.fold import fold_iteration_marks
    with pytest.raises(ValueError):
        fold_iteration_marks("時々", "keep")


@pytest.mark.parametrize("a,b", [
    ("が", "が"),          # combining voiced mark
    ("か゛", "が"),              # spacing voiced mark
    ("は゜", "ぱ"),              # spacing semi-voiced mark
    ("パ", "パ"),
    ("ウ゛ァイオリン", "ヴァイオリン"),
    ("ｳﾞｧｲｵﾘﾝ", "ヴァイオリン"),
    ("ト゛ラえもん", "ドラえもん"),
])
def test_voiced_marks_join_their_kana(a, b):
    assert fold(a) == fold(b)


def test_voiced_mark_without_precomposed_form_is_kept():
    assert width("あ゛") == "あ゙"
    assert fold("あ゛") != fold("あ")
    assert width("A ゛").endswith(" ゙")  # not after kana: left alone


def test_fold_steps_match_fold():
    from hondana import fold_steps
    for t in ["ﾊﾘｰ・ﾎﾟｯﾀｰ", "圖書館", "ＡＢＣ", "いすゞ"]:
        for kw in [{}, {"small_kana": True, "iteration_marks": "expand"}, {"punctuation": False, "han": False}]:
            assert fold_steps(t, **kw)[-1][1] == fold(t, **kw)
    assert fold_steps("") == []


def test_cli_explain(capsys):
    from hondana.__main__ import main
    assert main(["fold", "--explain", "--small-kana", "ﾊﾘｰ・ﾎﾟｯﾀｰ"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].split()[0] == "input" and out[-1].split() == ["punctuation", "はりぽつた"]
    assert any(l.startswith("small_kana") for l in out)


@pytest.mark.parametrize("a,b,kw", [
    ("圖書館", "図書館", {}),
    ("图书馆", "図書館", {}),
    ("ハリー・ポッター", "はりー ぽったー", {}),
    ("ﾊﾘｰ ﾎﾟｯﾀｰ", "ハリー・ポッター", {}),
    ("ＡＢＣ", "abc", {}),
    ("か゛", "が", {}),
    ("時々", "時時", {"iteration_marks": "expand"}),
])
def test_why_not_nfkc(a, b, kw):
    """The table in docs/why-not-nfkc.md: NFKC alone misses these, fold() doesn't."""
    import unicodedata
    assert unicodedata.normalize("NFKC", a) != unicodedata.normalize("NFKC", b)
    assert fold(a, **kw) == fold(b, **kw)


def test_fold_is_a_key_not_display_text():
    assert fold("コーヒー") == fold("コヒ")
