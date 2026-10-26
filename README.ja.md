# hondana 本棚

[中文](README.md) · [English](README.en.md)

日本語／中日の書誌データを「ちゃんと突き合わせる」ための小さな Python ライブラリです。依存ゼロ。

本の検索を作るとよくある話で、利用者は `图书馆` と打つのにデータは `圖書館`、`ﾊﾘｰ ﾎﾟｯﾀｰ` と打っても書名は `ハリー・ポッター`。hondana はこれらを同じ比較用キーにたたみます。ついでに ISBN 検索も入っていて、openBD → 国立国会図書館サーチ → Google Books → Open Library の順に問い合わせます。

> まだ骨組み段階です。字表は代表的な字を少しだけ入れたもので、網羅はしていません。追加の PR 歓迎です。

## インストール

```bash
pip install git+https://github.com/Jasonin2099/hondana
```

## 使い方

```python
from hondana import fold, to_isbn13, lookup

fold("圖書館") == fold("图书馆") == fold("図書館")   # True
fold("ﾊﾘｰ・ﾎﾟｯﾀｰ") == fold("はりー ぽったー")         # True
to_isbn13("4-00-310101-4")                           # '9784003101018'

book = lookup("9784003101018")    # ネットワークに出ます。見つからなければ None
print(book.title, book.source)
```

CLI：`python -m hondana fold "ＡＢＣ　入門"` ／ `python -m hondana isbn 9784003101018`

## `fold()` の中身

1. NFKC（全角英数→半角、半角カナ→全角）
2. 旧字体・繁体字・簡体字 → 新字体（`_tables.py` の小さな表）
3. カタカナ→ひらがな、長音符 `ー` を除去（`small_kana=True` で ぁ→あ、っ→つ も畳む。`iteration_marks="expand"`/`"drop"` で 々 ゝ ゞ を展開・削除）
4. 小文字化、空白・記号・「」『』を除去

各ステップは個別にオフにできます。机／機、干、后、叶 のように日本語では別の字になる簡体字は、別の本を混ぜないようあえて入れていません。

## ISBN 検索

ソースごとに独立して試すので、一つがタイムアウトしても残りは続行します。`fetch(url, params, timeout) -> (status, text)` を渡せば、HTTP クライアントの差し替え・キャッシュ・テスト用スタブが自由です。

ロードマップ：[ROADMAP.md](ROADMAP.md) ・ MIT License
