# hondana 本棚

[中文](README.md) · [日本語](README.ja.md)

Small, dependency-free Python helpers for matching Japanese / CJK book metadata.

If you've built book search you've seen it: the user types `图书馆`, the record says `圖書館`; someone types `ﾊﾘｰ ﾎﾟｯﾀｰ`, the title is `ハリー・ポッター`. hondana folds these into one comparison key. It also ships a tiny ISBN lookup that falls back openBD → NDL Search → Google Books → Open Library.

> Early skeleton: the character tables are a small starter set — enough to show the idea, not full coverage. Pairs welcome.

## Install

```bash
pip install git+https://github.com/Jasonin2099/hondana
```

## Use

```python
from hondana import fold, to_isbn13, lookup

fold("圖書館") == fold("图书馆") == fold("図書館")   # True
fold("ﾊﾘｰ・ﾎﾟｯﾀｰ") == fold("はりー ぽったー")         # True
to_isbn13("4-00-310101-4")                           # '9784003101018'

book = lookup("9784003101018")    # hits the network; None if nobody knows it
print(book.title, book.source)
```

CLI: `python -m hondana fold "ＡＢＣ　入門"` · `python -m hondana isbn 9784003101018`

## What `fold()` does

1. NFKC (full-width ASCII → half, half-width kana → full)
2. kyujitai / traditional / simplified → shinjitai (small table in `_tables.py`)
3. katakana → hiragana, drop the long-vowel mark `ー`
4. casefold, drop spaces, punctuation and 「」『』 brackets

Every step can be switched off (`fold(s, kana=False)` etc.). Simplified characters that are a *different* everyday Japanese character (机 vs 機, 干, 后, 叶) are left out on purpose.

## ISBN lookup

Each source is tried independently, so one timeout doesn't skip the rest. Pass your own `fetch(url, params, timeout) -> (status, text)` to use another HTTP client, add caching, or stub the network in tests.

## Tests

`pip install pytest && python -m pytest -q`

Roadmap: [ROADMAP.md](ROADMAP.md) · MIT License
