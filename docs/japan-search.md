# Japan Search (ジャパンサーチ)

[Japan Search](https://jpsearch.go.jp/) is the national aggregator run by the
National Diet Library: one search over 300+ databases from libraries, museums
and archives. Its [simple Web API](https://jpsearch.go.jp/api) is free, needs
no key and returns JSON. `hondana.jpsearch` is a small client for it that
**applies each database's own terms before you see a record**.

Status: the client, the terms handling and the attribution model are in
(`hondana.jpsearch`); `search(sources=(..., "jpsearch"))`,
`lookup(isbn, order=(..., "jpsearch"))` and `--source jpsearch` on the
`search` / `lookup` commands use it. Opt-in: the default sources are
unchanged.

## What the terms say

Checked against the Japan Search [site policy](https://jpsearch.go.jp/policy),
the [API guide](https://jpsearch.go.jp/static/developer/webapi/ch1_intro.html)
and the [metadata guidelines for partner institutions](https://jpsearch.go.jp/static/pdf/cooperation/jps_manual_202604.pdf):

- Conditions are set **per database**, not for Japan Search as a whole.
- Each database chooses how its metadata may be used through the API:
  API取得可能 / 一部項目利用不可 / API利用不可. The API reports this as
  `apiType`: `ok`, `restricted` or `ng`. For `restricted` databases the
  field definitions (`/api/database/{id}/label`) mark the unusable fields
  `storeType: guionly`.
- The metadata licence (`metadataRights`) is free text. When it is empty the
  metadata is CC0. Many databases use CC0 or CC BY; others use CC BY-SA,
  CC BY-NC-SA, 政府標準利用規約, their own terms page, or forbid reuse.
- Even for CC0 the site policy asks you to credit the source, e.g.
  「出典：ジャパンサーチ「全国書誌（国立国会図書館）」のメタデータ」, and to say so
  when you edited the data. It is a request, not a legal condition.
- There is a request limit with no published number; space your requests.

## What hondana does with that

| Database | Default |
|---|---|
| `apiType: ng` | always skipped |
| terms that forbid reuse (二次利用不可, 無断転載…禁止, …お断り) | always skipped |
| `apiType: restricted` | skipped; with `Policy(restricted=True)` used without its `guionly` fields |
| CC0, PDM, CC BY, PDL 1.0, 政府標準利用規約 | used |
| CC BY-SA, CC BY-NC*, CC BY-ND | skipped unless you add the licence to `Policy.accept` |
| own terms page, several licences, caveats (ただし…, …をご確認ください) | skipped unless you read them and list the id in `Policy.allow` |
| database not in the database list | skipped |

`allow` and `accept` never let `ng` or no-reuse databases through. Every
record carries `licence`, `attribution_required` (true for CC BY-type, PDL
and 政府標準利用規約 terms) and a ready-made `attribution` line. The line
points at the item page, or at the database page when the database says no
per-record notice is needed (NDL data: 個別のメタデータに表示を行う必要はありません).
Use `attribution(db, item_id, modified=True)` if you changed the data.

The classification reads the licence text conservatively: anything it cannot
place is `custom` and stays out until you decide. Check `js.skipped` (or pass
`on_skip`) to see which databases were left out and why.

## ISBN lookup

Keyword search on an ISBN is fuzzy on Japan Search (a search for one ISBN
returns hundreds of unrelated records), so `JapanSearch.search()` takes a
title and author. For an ISBN, `JapanSearch.lookup()` asks the
[SPARQL endpoint](https://jpsearch.go.jp/rdf/sparql/) for items whose
`schema:identifier` is exactly that ISBN. The RDF writes it as `ISBN:` plus
the ISBN-10 or ISBN-13, with or without hyphens (`ISBN:4-634-34250-2`,
`ISBN:4634342502`), so all four spellings are asked for at once
(`isbn_literals()`). Databases the policy skips are left out before their
items are fetched; each remaining item comes from `/api/item/{id}` and goes
through the same checks as a search hit. One SPARQL request plus one per
item; `lookup()` in hondana stops at the first record that passes.

Coverage is whatever the databases put in `schema:identifier`: mostly NDL
Digital Collections (dignl) and some library catalogues. The 全国書誌 (bibnl)
records carry a JPNO there instead, so for new books openBD / NDL Search
remain the better sources; Japan Search is an extra for older or digitised
books.

## Example

The network is stubbed here so the example runs offline; drop `fetch=` to
use the real API.

```python
import json
from hondana.jpsearch import JapanSearch, Policy

def stub(url, params, timeout):
    if url.endswith("/database/search"):
        return 200, json.dumps({"list": [
            {"id": "bibnl", "name": {"ja": "全国書誌"}, "apiType": "ok",
             "metadataRights": {"ja": "CC BY4.0で利用できます。個別のメタデータに表示を行う必要はありません。"}},
            {"id": "closed", "name": {"ja": "非公開DB"}, "apiType": "ng"},
        ]})
    if url.endswith("/organization/search"):
        return 200, json.dumps({"list": [{"id": "ndl", "name": {"ja": "国立国会図書館"}}]})
    if url.endswith("/item/search/jps-cross"):
        return 200, json.dumps({"list": [
            {"id": "bibnl-1", "common": {"id": "bibnl-1", "database": "bibnl", "provider": "ndl",
             "title": "吾輩は猫である", "contributor": ["夏目漱石 著"], "temporal": ["1990"]}},
            {"id": "closed-1", "common": {"id": "closed-1", "database": "closed", "title": "…"}},
        ]})
    return 404, ""

js = JapanSearch(fetch=stub, policy=Policy())
records = js.search(title="吾輩は猫である", author="夏目漱石")
r = records[0]
assert (r.title, r.year, r.licence, r.attribution_required) == ("吾輩は猫である", "1990", "cc-by", True)
assert r.attribution == "出典：ジャパンサーチ「全国書誌（国立国会図書館）」のメタデータ（https://jpsearch.go.jp/database/bibnl）"
assert len(records) == 1 and js.skipped == {"closed": "API use not allowed (apiType=ng)"}
book = r.to_book()  # a hondana Book, source "Japan Search"
```

## From `search()`

Add `"jpsearch"` to `sources`. Its books keep `licence` and `attribution`
(both empty for the other sources, and left out of `to_dict()` then), so the
credit line travels with the record. `jpsearch_policy` takes a `Policy`,
`on_skip` reports the databases left out. When an earlier source already
returned the same book (same ISBN, or same folded title and author), that
copy is kept — put `"jpsearch"` first if you prefer its records.

```python
import json
from hondana import search

def stub(url, params, timeout):
    if url.endswith("/database/search"):
        return 200, json.dumps({"list": [
            {"id": "zero", "name": {"ja": "ゼロ文庫"}, "provider": "ゼロ図書館", "apiType": "ok"},
            {"id": "nc", "name": {"ja": "非営利DB"}, "apiType": "ok", "metadataRights": {"ja": "CC BY-NC"}},
        ]})
    if url.endswith("/item/search/jps-cross"):
        return 200, json.dumps({"list": [
            {"id": "zero-7", "common": {"id": "zero-7", "database": "zero", "title": "猫の本", "temporal": ["1935"]}},
            {"id": "nc-1", "common": {"id": "nc-1", "database": "nc", "title": "猫の図鑑"}},
        ]})
    return 404, ""

skipped = {}
books = search("猫", sources=("jpsearch",), fetch=stub, on_skip=skipped.__setitem__)
b = books[0]
assert (b.title, b.source, b.licence) == ("猫の本", "Japan Search", "cc0")
assert b.attribution == "出典：ジャパンサーチ「ゼロ文庫（ゼロ図書館）」のメタデータ（https://jpsearch.go.jp/item/zero-7）"
assert len(books) == 1 and skipped == {"nc": "licence cc-by-nc not in Policy.accept"}
```

Exports put the metadata licence and the 出典 credit line into each record
(these describe the *metadata*, not the book's own copyright):

| Format | Licence | Credit line (出典) |
|---|---|---|
| BibTeX | `copyright` | `note` |
| RIS | an `N1` line `Licence: cc-by` (also accepts `License:`) | `N1` |
| CSL-JSON | `license` | `note` |

Records without either field export exactly as before. `loads()` reads the
fields back, and `dumps(loads(text))` is unchanged. Keep `book.attribution`
next to anything you publish in another form.

## From `lookup()`

```python
import json
from hondana import lookup

def stub(url, params, timeout):
    if url.endswith("/database/search"):
        return 200, json.dumps({"list": [{"id": "zero", "name": {"ja": "ゼロ文庫"}, "apiType": "ok"}]})
    if url.endswith("/rdf/sparql/"):
        assert '"ISBN:4-634-34250-2"' in params["query"]
        return 200, json.dumps({"results": {"bindings": [{"s": {"value": "https://jpsearch.go.jp/data/zero-3"}}]}})
    if url.endswith("/item/zero-3"):
        return 200, json.dumps({"id": "zero-3", "common": {"id": "zero-3", "database": "zero",
                                "title": "海の道と東西の出会い", "temporal": ["1998"]}})
    return 404, ""

b = lookup("4634342502", order=("jpsearch",), fetch=stub)
assert (b.isbn, b.year, b.source, b.licence) == ("9784634342507", "1998", "Japan Search", "cc0")
assert b.attribution.endswith("（https://jpsearch.go.jp/item/zero-3）")
```

With `merge=True` the credit line is kept on the merged book when at least
one of its fields came from Japan Search.

## From the command line

```sh
python -m hondana search --title 吾輩は猫である --author 夏目漱石 --source jpsearch
python -m hondana search 猫 --source ndl --source jpsearch --jp-restricted --jp-allow DB_ID --jp-accept cc-by-sa
python -m hondana lookup 9784003101018 --source openbd --source ndl --source jpsearch --merge
```

The table is followed by a 出典 / Sources block (one line per credit; NDL
data needs only one per database). `--format json` keeps `licence` and
`attribution` on every object; `bibtex` / `ris` / `csl` write them into the
record itself (see the table above). Skipped databases are reported on
stderr (`# jpsearch: skipped database … (reason)`). `--jp-deny DB` leaves a
database out.

To use a CC BY-SA database, or one with its own terms, after reading them:

```python
from hondana.jpsearch import DEFAULT_ACCEPT, Policy

policy = Policy(accept=DEFAULT_ACCEPT | {"cc-by-sa"}, allow=frozenset({"bjfl"}))
```
