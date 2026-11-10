# Recipes

Short, copy-pasteable answers to "I have this mess, what do I call?". Every
Python block on this page runs offline as written and is executed by
`tests/test_docs.py`, so it stays in sync with the code.

- [Clean and de-duplicate a book list](#clean-and-de-duplicate-a-book-list)
- [Search a catalogue the way people type](#search-a-catalogue-the-way-people-type)
- [Check the ISBNs in a paper's reference list](#check-the-isbns-in-a-papers-reference-list)
- [Fill in missing metadata](#fill-in-missing-metadata)
- [From the shell](#from-the-shell)

## Clean and de-duplicate a book list

A list exported from a spreadsheet, a library app and a hand-typed note usually
has the same book three times: different widths, old and new kanji, ISBN-10 vs
ISBN-13, with or without hyphens. Build a key from the ISBN when there is one,
and from the folded title + author when there isn't. Keep the original text for
display.

```python
import csv, io
from hondana import fold, to_isbn13

data = """title,author,isbn
吾輩は猫である,夏目漱石,4-00-310101-4
吾輩ハ猫デアル,夏目 漱石,9784003101018
ﾊﾘｰ･ﾎﾟｯﾀｰと賢者の石,J.K.ローリング,
ハリー・ポッターと賢者の石,J. K. ローリング,
「坊っちゃん」,夏目漱石,
"""

def key(row):
    isbn = to_isbn13(row["isbn"], strict=True)   # '' for empty or bad check digit
    if isbn:
        return ("isbn", isbn)
    return ("text", fold(row["title"]), fold(row["author"]))

seen = {}
for row in csv.DictReader(io.StringIO(data)):
    seen.setdefault(key(row), row)                # first spelling wins

titles = [r["title"] for r in seen.values()]
assert titles == ["吾輩は猫である", "ﾊﾘｰ･ﾎﾟｯﾀｰと賢者の石", "「坊っちゃん」"]
```

Notes:

- `to_isbn13(..., strict=True)` returns `""` for a typo'd check digit instead of
  silently "fixing" it, so a wrong ISBN never merges two different books. Rows
  with a bad ISBN fall back to the text key; flag them with `is_valid()` if you
  want to review them.
- `吾輩ハ猫デアル` and `吾輩は猫である` only fold together because the first row
  carried an ISBN. Text keys match spelling variants, not different wording.
- For a looser match add opt-ins: `fold(s, small_kana=True, itaiji=True,
  iteration_marks="expand")`. Use the same options on both sides.

## Search a catalogue the way people type

Fold the catalogue once, fold each query, compare with `in`. That is enough for
"starts typing a title in any script and the right book shows up".

```python
from hondana import fold

catalogue = ["圖書館戦争", "ハリー・ポッターと賢者の石", "コーヒーが冷めないうちに", "時々、ボソッとロシア語でデレる"]
index = [(fold(t, iteration_marks="expand"), t) for t in catalogue]

def search(q):
    k = fold(q, iteration_marks="expand")
    return [t for folded, t in index if k and k in folded]

assert search("図書館") == ["圖書館戦争"]            # new form finds old form
assert search("图书馆") == ["圖書館戦争"]            # simplified too
assert search("ﾊﾘｰ ﾎﾟｯﾀｰ") == ["ハリー・ポッターと賢者の石"]
assert search("こーひー") == ["コーヒーが冷めないうちに"]
assert search("時時") == ["時々、ボソッとロシア語でデレる"]
```

`fold()` throws away `ー`, punctuation and case, so short queries over-match
(`コヒ` hits `コーヒー`). For ranking, compare the folded strings first and fall back
to the original text to break ties.

## Check the ISBNs in a paper's reference list

Pull every ISBN out of a bibliography, normalise it, and print it hyphenated.
`find_isbns()` only returns ISBNs with a valid check digit, so anything you can
see in the text but not in the result is worth a second look.

```python
import re
from hondana import find_isbns, hyphenate

refs = """
[1] 夏目漱石『吾輩は猫である』岩波書店, 1990. ISBN 4-00-310101-4
[2] 同上, ＩＳＢＮ９７８－４－００－３１０１０１－８（全角で書かれたもの）
[3] Dostoevsky, F. Crime and Punishment. Penguin, 2003. ISBN978-0-14-044913-6
[4] 誤植のある例. ISBN 978-4-00-310101-9
"""

found = find_isbns(refs)                     # de-duplicated, ISBN-13
assert [hyphenate(i) for i in found] == ["978-4-00-310101-8", "978-0-14-044913-6"]

# Lines that mention an ISBN but yielded nothing valid:
suspect = [line for line in refs.splitlines() if re.search(r"ISBN|ＩＳＢＮ", line) and not find_isbns(line)]
assert suspect == ["[4] 誤植のある例. ISBN 978-4-00-310101-9"]
```

`hyphenate()` knows the Japan (978-4), English-language (978-0, 978-1), China
(978-7) and Taiwan (978-957, 978-986) groups; other groups come back un-hyphenated
rather than guessed.

## Fill in missing metadata

`lookup_many()` queries the sources in order, one ISBN after another, and keeps
the input order in its result (`None` where nothing was found). In real use you
drop the `fetch=` argument and it goes to the network; here a tiny fake stands in
for openBD so the example runs offline.

```python
import json
from hondana import cached, lookup_many

def fake_fetch(url, params, timeout):
    if "openbd" in url and params["isbn"] == "9784003101018":
        return 200, json.dumps([{"summary": {"title": "吾輩は猫である", "author": "夏目漱石",
                                             "publisher": "岩波書店", "pubdate": "19900401"}}])
    return 404, ""

fetch = cached(fake_fetch, ttl=24 * 3600)     # repeat ISBNs don't hit the API twice
books = lookup_many(["4-00-310101-4", "978-4-00-310101-8", "not an isbn"], fetch=fetch, rate=0)

assert [b.title if b else None for b in books] == ["吾輩は猫である", "吾輩は猫である", None]
assert books[0].to_dict()["year"] == "1990"
```

For real runs:

- Keep `rate` at `0.5`–`1` seconds or more; these are free public APIs.
- `merge=True` fills empty fields (publisher, year…) from later sources, at the
  cost of querying all of them.
- Pass `on_error=lambda name, err: print(name, err)` to see which source failed
  and why, and `timeouts={"ndl": 30}` if NDL Search is slow from where you are.

## From the shell

The CLI reads its text from arguments or stdin, so it fits into pipes:

```bash
# Every valid ISBN in a manuscript, one per line, hyphenated
# (--find scans even when the input is a single word)
python -m hondana isbn --find < paper.txt

# Look them all up and print a table
python -m hondana isbn --find < paper.txt | xargs python -m hondana lookup --merge --format table

# Why do these two titles (not) match?
python -m hondana fold --explain "ﾊﾘｰ・ﾎﾟｯﾀｰ"
```
