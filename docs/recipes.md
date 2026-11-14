# Recipes

Short, copy-pasteable answers to "I have this mess, what do I call?". Every
Python block on this page runs offline as written and is executed by
`tests/test_docs.py`, so it stays in sync with the code.

- [Clean and de-duplicate a book list](#clean-and-de-duplicate-a-book-list)
- [Search a catalogue the way people type](#search-a-catalogue-the-way-people-type)
- [Check the ISBNs in a paper's reference list](#check-the-isbns-in-a-papers-reference-list)
- [Fill in missing metadata](#fill-in-missing-metadata)
- [Search by title or author](#search-by-title-or-author)
- [From the shell](#from-the-shell)

## Clean and de-duplicate a book list

A list exported from a spreadsheet, a library app and a hand-typed note usually
has the same book three times: different widths, old and new kanji, ISBN-10 vs
ISBN-13, with or without hyphens. Build a key from the ISBN when there is one,
and from the folded title + author when there isn't. Keep the original text for
display.

```python
import csv, io
from hondana import dedupe

data = """title,author,isbn
吾輩は猫である,夏目漱石,4-00-310101-4
吾輩ハ猫デアル,夏目 漱石,9784003101018
ﾊﾘｰ･ﾎﾟｯﾀｰと賢者の石,J.K.ローリング,
ハリー・ポッターと賢者の石,J. K. ローリング,
「坊っちゃん」,夏目漱石,
"""

result = dedupe(csv.DictReader(io.StringIO(data)))
titles = [r["title"] for r in result.unique]
assert titles == ["吾輩は猫である", "ﾊﾘｰ･ﾎﾟｯﾀｰと賢者の石", "「坊っちゃん」"]
assert result.extra == 2
```

Notes:

- A valid ISBN (strict check digit) groups rows together; otherwise the key is
  the folded title + author. A row with an ISBN also joins any text-only row
  with the same folded title + author, so `吾輩ハ猫デアル` without an ISBN still
  meets `吾輩は猫である`.
- `to_isbn13(..., strict=True)` is used under the hood, so a typo'd check digit
  never merges two different books — those rows fall back to the text key.
  Flag them with `is_valid()` if you want to review them.
- Text keys match spelling variants, not different wording.
- For a looser match pass the same `fold()` opt-ins through to `dedupe`
  (`small_kana=True`, `itaiji=True`, `iteration_marks="expand"`, …).
- From the shell: `python -m hondana dedupe books.csv` reports the groups;
  `python -m hondana dedupe books.csv --unique clean.csv` writes the first
  spelling of each. Column names like `書名` / `著者` / `ISBN` are detected.

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

`hyphenate()` uses compact tables generated from the ISBN International
Agency's RangeMessage.xml (Japan, English-language, China, Taiwan, and also
978-2, 978-3, 978-89, 979-…, and the rest of the official groups). Unassigned
ranges still come back un-hyphenated rather than guessed. Refresh the tables
with `python3 scripts/update_isbn_ranges.py` (the XML itself is not vendored).

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


## Search by title or author

When you do not have an ISBN, `search()` queries NDL Search and Open Library
and ranks the hits with `fold()`, so typographic variants of the same title
float to the top. A tiny fake stands in for the network here, as in the other
recipes.

```python
import json
from hondana import search

def fake_fetch(url, params, timeout):
    if "ndlsearch" in url:
        return 200, """<rss><item>
            <title>吾輩は猫である</title>
            <dc:creator>夏目, 漱石</dc:creator>
            <dc:publisher>岩波書店</dc:publisher>
            <dcterms:issued>1990</dcterms:issued>
            <dc:identifier>ISBN 978-4-00-310101-8</dc:identifier>
        </item></rss>"""
    if "openlibrary.org/search" in url:
        return 200, json.dumps({"docs": [
            {"title": "I Am a Cat", "author_name": ["Natsume Soseki"],
             "first_publish_year": 1970, "isbn": ["9780804832410"]}
        ]})
    return 404, ""

hits = search("吾輩は猫である", fetch=fake_fetch, limit=5)
assert hits[0].title == "吾輩は猫である" and hits[0].source == "NDL"
assert hits[0].isbn == "9784003101018"
assert any(h.title == "I Am a Cat" for h in hits)
```

`search("吾輩は猫である", author="夏目漱石")` also works, or pass `title=` and
`author=` separately. From the shell: `python -m hondana search "吾輩は猫である"`.

When openBD has classification data, `lookup()` fills `Book.ccode` (the 4-digit
Japanese C-code, without a leading C) and `Book.ndc`. ONIX subject scheme 79 is
the bookseller genre code and is not treated as NDC.

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

# Title search, no ISBN
python -m hondana search "吾輩は猫である"
```

## Export a reference list

`lookup()` returns a `Book`; turn that into something a citation manager
or a `.bib` file can eat. BibTeX, RIS and CSL-JSON are written in the
library itself — the usual converters (bibtexparser, rispy, citeproc-py,
betterbib) would have added dependencies, and `Book` only has a handful
of fields to map.

```python
from hondana import Book, dumps, to_bibtex, to_csl, to_ris

book = Book(
    isbn="9784003101018",
    title="吾輩は猫である",
    author="夏目漱石／著",
    publisher="岩波書店",
    year="1990",
)

bib = to_bibtex(book)
assert "@book{isbn9784003101018," in bib
assert "author = {夏目漱石}" in bib          # the trailing ／著 is dropped
assert "isbn = {978-4-00-310101-8}" in bib

assert "TY  - BOOK" in to_ris(book)
assert to_csl(book)["author"] == [{"literal": "夏目漱石"}]
assert to_csl(book)["issued"] == {"date-parts": [[1990]]}

# Several books at once (CSL-JSON becomes a JSON array):
other = Book(isbn="9780140449136", title="Crime and Punishment",
             author="Dostoyevsky, Fyodor", publisher="Penguin", year="2003")
csl = dumps([book, other], "csl")
assert csl.strip().startswith("[")
```

From the shell: `python -m hondana lookup --format bibtex 9784003101018`
(also `--format ris` and `--format csl`).
