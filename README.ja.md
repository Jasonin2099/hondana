# hondana 本棚

[中文](README.md) · [English](README.en.md)

日本語／中日の書誌データを「ちゃんと突き合わせる」ための小さな Python ライブラリです。依存ゼロ。

本の検索を作るとよくある話で、利用者は `图书馆` と打つのにデータは `圖書館`、`ﾊﾘｰ ﾎﾟｯﾀｰ` と打っても書名は `ハリー・ポッター`。hondana はこれらを同じ比較用キーにたたみます。ついでに ISBN 検索も入っていて、openBD → 国立国会図書館サーチ → Google Books → Open Library の順に問い合わせます。

> 字表はよく使う字を集めた起点で、書名や人名のかなりをカバーしますが、網羅はしていません。追加の PR を歓迎します。

## インストール

```bash
pip install hondana-ja
# または: pip install git+https://github.com/Jasonin2099/hondana
```

## 使い方

```python
from hondana import fold, to_isbn13, hyphenate, registration_group, decode_ccode, ndc_class, lookup, lookup_many, search, dedupe, to_bibtex, to_ris, to_csl, loads

fold("圖書館") == fold("图书馆") == fold("図書館")   # True
fold("ﾊﾘｰ・ﾎﾟｯﾀｰ") == fold("はりー ぽったー")         # True
to_isbn13("4-00-310101-4")                           # '9784003101018'
hyphenate("9784003101018")                           # '978-4-00-310101-8'（公式の ISBN レンジメッセージに基づく。978-2 / 978-3 / 978-89、979-… も含む。更新は scripts/update_isbn_ranges.py）
registration_group("9784003101018")                  # ('978-4', 'Japan')（同じレンジメッセージの登録グループ名。英語表記）
decode_ccode("C0093")                                 # CCode(code='0093', audience='一般', form='単行本', subject='文学', detail='日本文学、小説・物語')
ndc_class("913.6")                                    # NdcClass(code='913.6', main='9', label='文学', label_en='Literature')（0〜9 の類だけ）

book = lookup("9784003101018")                       # ネットワークに出ます。見つからなければ None
book = lookup("9784003101018", merge=True)           # 欠けた項目を後続ソースで補完
books = lookup_many(["978…", "978…"], rate=0.5)      # まとめて検索。rate は間隔（秒）
print(book.title, book.source, book.ccode, book.ndc)  # ccode / ndc は openBD 由来。無ければ空
print(book.ccode_info, book.ndc_info, book.cover)  # C コードの解読（to_dict() では ccode_labels）。NDC の類（to_dict() では ndc_class）。cover は openBD などの書影 URL（画像はダウンロードしない）
hits = search("吾輩は猫である")                  # ISBN なし：NDL サーチと Open Library。fold() で順位付け
print(to_bibtex(book))   # to_ris(book)、to_csl(book)、book.to_bibtex() も可
books = loads(open("list.bib", encoding="utf-8").read())  # hondana が書き出した BibTeX / RIS / CSL-JSON を読み戻す（形式は自動判定。ライセンスと出典表示があればそれも含む。汎用パーサではない）
```

CLI：`fold "ＡＢＣ　入門"` ／ `fold --explain …` ／ `isbn 978…`（検証・ハイフン付け、ネット不要）／ `isbn "文中の ISBN…"` ／ `isbn --group 978…`（登録グループ名をタブ区切りで併記。`--json` では `group` / `group_name`）／ `ccode C0093 3055`（C コードを販売対象・発行形態・内容に解読、ネット不要）／ `ndc 913.6 007`（NDC 分類記号の類、0 総記〜9 文学、ネット不要）／ `lookup 978…` ／ `lookup --merge --format table 978… 978…` ／ `lookup --format bibtex 978…`（`ris` / `csl` も可）／ `isbn --find < paper.txt | lookup`（標準入力から ISBN を読む。間隔は既定 0.5 秒、`--rate` で変更）／ `search "吾輩は猫である"`（書名・著者検索。`--title` / `--author` も可。`--source jpsearch` でジャパンサーチも検索、データベースごとの条件で絞り込み、表の下に出典を表示。`lookup --source …` も同様）／ `dedupe books.csv`（ISBN、または畳んだ書名+著者で重複グループを報告。`--unique clean.csv` で先頭表記を書き出す）／ `convert list.ris --to bibtex`（hondana が書き出した BibTeX / RIS / CSL-JSON を読み戻して別形式に。既定は JSON、`--from` で入力形式を指定）

## `fold()` の中身

1. NFKC（全角英数→半角、半角カナ→全角）
2. 旧字体・繁体字・簡体字 → 新字体（`_tables.py` の小さな表）
3. カタカナ→ひらがな、長音符 `ー` を除去（`small_kana=True` で ぁ→あ、っ→つ も畳む。`iteration_marks="expand"`/`"drop"` で 々 ゝ ゞ を展開・削除。`itaiji=True` で人名に多い異体字 髙→高、﨑→崎 を畳む。`dashes=True` で長音符・波ダッシュ・各種ダッシュを統一、コ─ヒ─→コーヒー）
4. 小文字化、空白・記号・「」『』を除去

各ステップは個別にオフにできます。机／機、干、后、叶 のように日本語では別の字になる簡体字は、別の本を混ぜないようあえて入れていません。

NFKC だけでは足りない理由は [docs/why-not-nfkc.md](docs/why-not-nfkc.md)（英語・対照表つき）。

よくある使い方（書籍リストの整理と重複除去、入力どおりの目録検索、論文の参考文献の ISBN チェック、書誌情報の一括補完、シェルでのパイプ）は [docs/recipes.md](docs/recipes.md)（英語。サンプルはすべてテストで実行）。

## ISBN 検索

ソースごとに独立して試すので、一つがタイムアウトしても残りは続行します。`merge=True` は `order` の全ソースを問い合わせ、項目ごとに最初の非空値を採用します（`source` は `openBD+NDL` のように連結）。`lookup_many()` は入力順に一括検索し、`rate` で間隔（秒）を指定できます。`fetch(url, params, timeout) -> (status, text)` を渡せば、HTTP クライアントの差し替え・キャッシュ・テスト用スタブが自由です。メモリ上の簡易 TTL キャッシュは `lookup(isbn, fetch=cached(ttl=3600))` で使えます。openBD に分類があれば `Book.ccode`（日本図書コードの C コード、先頭の C は付けない）と `Book.ndc` に入ります。`decode_ccode()` / `Book.ccode_info` は C コードを販売対象・発行形態・内容（大分類・中分類）のラベルに変換します。表は日本図書コード管理センター『利用の手引き 2025年版』p.24 の分類記号一覧表に準拠し、空欄（リザーブ）の中分類は `detail` が空になります。C コードは出版者が選ぶ棚分けの目安で、図書館の分類ではありません。`ndc_class()` / `Book.ndc_info` は NDC 分類記号の 1 桁目、つまり第1次区分（類目）の 10 区分だけを付けます（0 総記、1 哲学、2 歴史、3 社会科学、4 自然科学、5 技術、6 産業、7 芸術、8 言語、9 文学。日本図書館協会の公開ページの表記）。`913.6`、全角数字、`NDC10:` などの前置きを受け付けます。NDC の分類表は日本図書館協会の著作物なので、綱目以下は同梱しません。ISBN がなく書名や著者だけで探すときは `search()` です。既定では国立国会図書館と Open Library を引き、結果を `fold()` で並べます。

ジャパンサーチ：`hondana.jpsearch.JapanSearch` は、データベースごとの利用条件を先に適用してから結果を返します。API利用不可・二次利用不可のデータベースは常に除外、一部項目利用不可のデータベースは明示したときだけ、利用不可の項目を除いて使います。その他のライセンスや独自規約は、内容を確認して許可したものだけ。各レコードにライセンスと出典表示の文言が付きます。`search(sources=(…, "jpsearch"))` と `lookup(isbn, order=(…, "jpsearch"))`（SPARQL エンドポイントで ISBN を完全一致検索）で検索元に追加できます（既定では使いません）。結果の `Book` には `licence` と `attribution`（出典表示）が残ります。BibTeX / RIS / CSL-JSON に書き出すときは、ライセンスと出典がレコードに入ります（BibTeX の `copyright` / `note`、RIS の `N1`、CSL の `license` / `note`）。出典のない記録の出力は以前と同一です。詳しくは [docs/japan-search.md](docs/japan-search.md)（英語）。

ロードマップ：[ROADMAP.md](ROADMAP.md) ・ MIT License
