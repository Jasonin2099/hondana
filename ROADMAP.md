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
- [ ] Publish to PyPI (trusted publishing via GitHub Actions)
- [x] Docs: a short "why not just NFKC?" section with examples (docs/why-not-nfkc.md)

## Next batch

- [ ] Add 20 more kyujitai → shinjitai pairs common in names and places (澤→沢, 廣→広 …)
- [ ] `fold()`: opt-in itaiji folding (髙→高, 﨑→崎 …)
- [ ] `fold()`: opt-in unification of long-vowel marks, tildes and dash variants
- [ ] `fold()`: katakana ⇄ hiragana as its own option
- [ ] ISBN: hyphenation for English-language groups (978-0, 978-1)
- [ ] ISBN: hyphenation for 978-7 and 978-986 / 978-957
- [ ] ISBN: `to_isbn10()` / `to_isbn13()` conversion with check-digit validation
- [ ] Lookup: merge results across sources, filling missing fields
- [ ] Lookup: batch lookup for many ISBNs with built-in rate limiting
- [ ] CLI: `hondana isbn` — find, validate and hyphenate ISBNs in text
- [ ] CLI: `hondana lookup` with JSON or table output
- [ ] Docs: practical recipes (cleaning a book list, reference lists in papers)
