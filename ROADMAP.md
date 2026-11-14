# Roadmap

Small steps, roughly one per day. Tick them off as they land.

- [x] Add GitHub Actions CI (Python 3.9–3.14, Windows)
- [x] Add 20 more kyujitai → shinjitai pairs (with tests)
- [x] Add 20 more simplified → shinjitai pairs, keep the "different character" exclusion list documented
- [x] `fold()`: option to fold small kana (ぁ→あ, っ→つ) for fuzzy matching
- [x] `fold()`: fold iteration marks (々 ゝ ゞ) — expand or drop, configurable
- [x] Handle voiced/semi-voiced combining marks (U+3099/U+309A) and spacing ゛ ゜ explicitly, with tests
- [x] ISBN: hyphenate ISBN-13 by registration group (978-4 Japan done; other groups later)
- [x] ISBN: `find_isbns()` should also catch "ISBN-10:" / "ISBN978…" without spaces, full-width digits and typographic dashes
- [x] Lookup: optional simple in-memory TTL cache wrapper for `fetch` (`cached()`)
- [x] Lookup: per-source timeout overrides (`timeouts={"ndl": 30}`)
- [x] Lookup: return the raw source payload behind a flag for debugging (`lookup(..., raw=True)` → `Book.raw`)
- [x] Lookup: add CiNii Books as an optional source
- [x] CLI: `hondana fold --explain` showing each step's output (`fold_steps()` in the API)
- [x] Type hints pass `mypy --strict` (checked in CI)
- [x] Publish to PyPI (trusted publishing via GitHub Actions)
- [x] Docs: a short "why not just NFKC?" section with examples (docs/why-not-nfkc.md)

## Next batch

- [x] Add 20 more kyujitai → shinjitai pairs common in names and places (澤→沢, 廣→広 …)
- [x] `fold()`: opt-in itaiji folding (髙→高, 﨑→崎 …)
- [x] `fold()`: opt-in unification of long-vowel marks, tildes and dash variants (`dashes=True`)
- [x] `fold()`: katakana ⇄ hiragana as its own option (`kana="hira"|"kata"|False`)
- [x] ISBN: hyphenation for English-language groups (978-0, 978-1)
- [x] ISBN: hyphenation for 978-7 and 978-986 / 978-957
- [x] ISBN: `to_isbn10()` / `to_isbn13()` conversion with check-digit validation
- [x] Lookup: merge results across sources, filling missing fields
- [x] Lookup: batch lookup for many ISBNs with built-in rate limiting
- [x] CLI: `hondana isbn` — find, validate and hyphenate ISBNs in text
- [x] CLI: `hondana lookup` with JSON or table output
- [x] Docs: practical recipes (cleaning a book list, reference lists in papers) — docs/recipes.md, examples run in tests/test_docs.py

## Batch 3 (toward 0.3.0)

Research existing tools first (bibtex/CSL libraries, isbnlib range data) before building.

- [x] Export: `Book` → BibTeX, RIS, CSL-JSON; CLI `hondana lookup --format bibtex|ris|csl`
- [x] CLI: `hondana dedupe books.csv` — dedupe by ISBN or folded title + author, report duplicate groups
- [x] ISBN: generate hyphenation ranges from the ISBN International RangeMessage.xml (covers 978-3, 978-2, 978-89, 979-…), with an update script
- [x] Lookup: search by title / author without ISBN (NDL Search, Open Library), results ranked with `fold()`
- [x] openBD: parse Japanese C-code and NDC into optional `Book` fields
- [x] Release 0.3.0 (GitHub Release → PyPI)
