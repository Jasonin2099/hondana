# hondana 本棚

[中文](README.md) · [日本語](README.ja.md)

Small, dependency-free Python helpers for matching Japanese / CJK book metadata.

If you've built book search you've seen it: the user types `图书馆`, the record says `圖書館`; someone types `ﾊﾘｰ ﾎﾟｯﾀｰ`, the title is `ハリー・ポッター`. hondana folds these into one comparison key. It also ships a tiny ISBN lookup that falls back openBD → NDL Search → Google Books → Open Library.

> Early skeleton: the character tables are a small starter set — enough to show the idea, not full coverage. Pairs welcome.

## Install

```bash
pip install hondana-ja
# or: pip install git+https://github.com/Jasonin2099/hondana
```

## Use

```python
from hondana import fold, to_isbn13, hyphenate, lookup, lookup_many, search, dedupe, to_bibtex, to_ris, to_csl

fold("圖書館") == fold("图书馆") == fold("図書館")   # True
fold("ﾊﾘｰ・ﾎﾟｯﾀｰ") == fold("はりー ぽったー")         # True
to_isbn13("4-00-310101-4")                           # '9784003101018'
hyphenate("9784003101018")                           # '978-4-00-310101-8' (from the official ISBN range message, including 978-2/3/89 and 979-…; refresh with scripts/update_isbn_ranges.py)

book = lookup("9784003101018")                       # hits the network; None if nobody knows it
book = lookup("9784003101018", merge=True)           # fill missing fields from later sources
books = lookup_many(["978…", "978…"], rate=0.5)      # batch; rate = min seconds between lookups
print(book.title, book.source, book.ccode, book.ndc)  # C-code / NDC from openBD, empty if absent
hits = search("吾輩は猫である")                  # no ISBN: NDL Search + Open Library, ranked with fold()
print(to_bibtex(book))   # or to_ris(book), to_csl(book); also book.to_bibtex()
```

CLI: `python -m hondana fold "ＡＢＣ　入門"` · `fold --explain …` · `isbn 978…` (validate/hyphenate, no network) · `isbn "text with ISBN…"` · `lookup 978…` · `lookup --merge --format table 978… 978…` · `lookup --format bibtex 978…` (also `ris` / `csl`) · `isbn --find < paper.txt | lookup` (ISBNs from stdin, 0.5 s between lookups by default, `--rate` to change) · `search "吾輩は猫である"` (title/author search; also `--title` / `--author`) · `dedupe books.csv` (duplicate groups by ISBN or folded title + author; `--unique clean.csv` writes the first spelling of each)

## What `fold()` does

1. NFKC (full-width ASCII → half, half-width kana → full)
2. kyujitai / traditional / simplified → shinjitai (small table in `_tables.py`)
3. katakana → hiragana, drop the long-vowel mark `ー` (opt-in: `small_kana=True` also folds ぁ→あ, っ→つ; `iteration_marks="expand"`/`"drop"` handles 々 ゝ ゞ; `itaiji=True` folds variant kanji common in names, 髙→高, 﨑→崎; `dashes=True` unifies long-vowel marks, tildes and dash variants, コ─ヒ─→コーヒー)
4. casefold, drop spaces, punctuation and 「」『』 brackets

Every step can be switched off (`fold(s, kana=False)` etc.). Simplified characters that are a *different* everyday Japanese character (机 vs 機, 干, 后, 叶) are left out on purpose.

Why not just NFKC? See [docs/why-not-nfkc.md](docs/why-not-nfkc.md).

Recipes (cleaning and de-duplicating a book list, searching a catalogue the way people type, checking the ISBNs in a reference list, filling in missing metadata, shell pipelines): [docs/recipes.md](docs/recipes.md). Every example there is run by the test suite.

## ISBN lookup

Each source is tried independently, so one timeout doesn't skip the rest. `merge=True` queries every source in `order` and fills missing fields (first non-empty wins; `source` becomes e.g. `openBD+NDL`). `lookup_many()` looks up many ISBNs in order; `rate` sets the minimum seconds between lookups. Pass your own `fetch(url, params, timeout) -> (status, text)` to use another HTTP client, add caching, or stub the network in tests. `cached(fetch, ttl=3600)` wraps any fetch with an in-memory TTL cache: `lookup(isbn, fetch=cached())`. When openBD includes classification, `Book.ccode` (Japanese C-code, without a leading C) and `Book.ndc` are filled in. `search()` looks up a title or author with no ISBN, via NDL Search and Open Library, and ranks hits with `fold()`.

## Tests

`pip install pytest && python -m pytest -q`

Roadmap: [ROADMAP.md](ROADMAP.md) · MIT License
