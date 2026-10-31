"""Character tables used by :mod:`hondana.fold`.

All tables map *to* the modern Japanese form (shinjitai), so that a title typed
in simplified Chinese, traditional Chinese, kyujitai or modern Japanese ends up
with the same key. This is a starter set, deliberately small and conservative: only pairs
that are unambiguous in bibliographic text are listed. PRs adding pairs are
welcome — please add a test case alongside.

Some simplified characters are also ordinary Japanese characters with a
different meaning (机 desk vs 機 machine, 干, 后, 叶, 征). Those are left out on
purpose: folding them would merge records that are not the same book. They are
listed in :data:`SIMP_EXCLUDED` so a future PR doesn't add them by accident.
"""

# kyujitai / traditional -> shinjitai
_KYU = (
    "亞亜 惡悪 圍囲 爲為 醫医 驛駅 圓円 應応 櫻桜 假仮 價価 畫画 會会 學学 樂楽 關関 氣気 舊旧 區区 經経 "
    "藝芸 檢検 廣広 號号 國国 濟済 實実 寫写 圖図 數数 聲声 戰戦 對対 體体 臺台 鐵鉄 傳伝 讀読 發発 變変 "
    "萬万 譯訳 藥薬 與与 來来 禮礼 歷歴 戀恋 灣湾 澤沢 "
    "惠恵 榮栄 衞衛 鹽塩 歐欧 穩穏 擴拡 覺覚 勸勧 卷巻 歡歓 縣県 險険 權権 顯顕 嚴厳 處処 壽寿 從従 燒焼 "
    "濱浜 邊辺 齋斎 齊斉 瀧滝 德徳 眞真 靜静 淺浅 豐豊 繩縄 驒騨 莊荘 彌弥 稻稲 澁渋 鄕郷 藏蔵 寶宝 黑黒"
)

# simplified Chinese -> shinjitai (only where it is not already shinjitai)
_SIMP = (
    "书書 东東 车車 长長 门門 马馬 鱼魚 鸟鳥 语語 说説 话話 读読 记記 论論 历歴 华華 汉漢 业業 电電 图図 "
    "馆館 为為 发発 经経 济済 对対 关関 时時 间間 问問 开開 题題 页頁 风風 见見 观観 现現 实実 "
    "选選 编編 译訳 简簡 类類 杂雑 "
    "计計 认認 识識 诗詩 证証 乐楽 线線 纪紀 级級 红紅 绘絵 续続 统統 战戦 剧劇 场場 银銀 铁鉄 农農 岁歳"
)

# Simplified forms that must NOT be folded, because the same code point is an
# ordinary Japanese character with its own meaning. Character -> why.
SIMP_EXCLUDED = {
    "机": "desk in Japanese; simplified for 機 (machine)",
    "干": "dry/shield in Japanese; simplified for 乾 and 幹",
    "后": "empress in Japanese; simplified for 後 (after)",
    "叶": "to grant (かなう) in Japanese; simplified for 葉 (leaf)",
    "征": "to conquer in Japanese; simplified for 徵/徴 (sign)",
    "云": "to say (いう) in Japanese; simplified for 雲 (cloud)",
    "芸": "arts in Japanese (shinjitai of 藝); simplified 芸 is a herb name",
    "广": "a radical (まだれ) in Japanese; simplified for 廣/広",
}


def _pairs(s: str) -> "dict[str, str]":
    out: "dict[str, str]" = {}
    for tok in s.split():
        if len(tok) == 2 and tok[0] != tok[1]:
            out[tok[0]] = tok[1]
    return out


KYU_TO_SHIN = _pairs(_KYU)
SIMP_TO_SHIN = {k: v for k, v in _pairs(_SIMP).items() if k not in SIMP_EXCLUDED}
HAN_MAP = {**SIMP_TO_SHIN, **KYU_TO_SHIN}

# itaiji (variant forms) -> standard form, used only with fold(..., itaiji=True).
# Mostly seen in personal and place names, where a catalogue may store either
# form for the same person. Off by default: some people insist on the variant.
_ITAIJI = "髙高 﨑崎 嵜崎 𠮷吉 邉辺 濵浜 栁柳 冨富"
ITAIJI = _pairs(_ITAIJI)

# iteration / variant marks that should vanish or be unified for matching
EXTRA_FOLD = {
    "〜": "~", "～": "~", "―": "-", "‐": "-", "−": "-", "–": "-", "—": "-",
    "「": "", "」": "", "『": "", "』": "", "【": "", "】": "", "《": "", "》": "", "〈": "", "〉": "",
    "ヴ": "ゔ",
}
