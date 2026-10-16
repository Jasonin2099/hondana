"""Character tables used by :mod:`hondana.fold`.

All tables map *to* the modern Japanese form (shinjitai), so that a title typed
in simplified Chinese, traditional Chinese, kyujitai or modern Japanese ends up
with the same key. This is a starter set, deliberately small and conservative: only pairs
that are unambiguous in bibliographic text are listed. PRs adding pairs are
welcome — please add a test case alongside.

Some simplified characters are also ordinary Japanese characters with a
different meaning (机 desk vs 機 machine, 干, 后, 叶, 征). Those are left out on
purpose: folding them would merge records that are not the same book.
"""

# kyujitai / traditional -> shinjitai
_KYU = (
    "亞亜 惡悪 圍囲 爲為 醫医 驛駅 圓円 應応 櫻桜 假仮 價価 畫画 會会 學学 樂楽 關関 氣気 舊旧 區区 經経 "
    "藝芸 檢検 廣広 號号 國国 濟済 實実 寫写 圖図 數数 聲声 戰戦 對対 體体 臺台 鐵鉄 傳伝 讀読 發発 變変 "
    "萬万 譯訳 藥薬 與与 來来 禮礼 歷歴 戀恋 灣湾 澤沢"
)

# simplified Chinese -> shinjitai (only where it is not already shinjitai)
_SIMP = (
    "书書 东東 车車 长長 门門 马馬 鱼魚 鸟鳥 语語 说説 话話 读読 记記 论論 历歴 华華 汉漢 业業 电電 图図 "
    "馆館 为為 发発 经経 济済 对対 关関 时時 间間 问問 开開 题題 页頁 风風 见見 观観 现現 实実 写写 "
    "门門 选選 编編 译訳 简簡 类類 杂雑"
)


def _pairs(s):
    out = {}
    for tok in s.split():
        if len(tok) == 2 and tok[0] != tok[1]:
            out[tok[0]] = tok[1]
    return out


KYU_TO_SHIN = _pairs(_KYU)
SIMP_TO_SHIN = _pairs(_SIMP)
HAN_MAP = {**SIMP_TO_SHIN, **KYU_TO_SHIN}

# iteration / variant marks that should vanish or be unified for matching
EXTRA_FOLD = {
    "〜": "~", "～": "~", "―": "-", "‐": "-", "−": "-", "–": "-", "—": "-",
    "「": "", "」": "", "『": "", "』": "", "【": "", "】": "", "《": "", "》": "", "〈": "", "〉": "",
    "ヴ": "ゔ",
}
