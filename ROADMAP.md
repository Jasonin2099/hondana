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
- [ ] Lookup: add CiNii Books as an optional source
- [x] CLI: `hondana fold --explain` showing each step's output (`fold_steps()` in the API)
- [x] Type hints pass `mypy --strict` (checked in CI)
- [ ] Publish to PyPI (trusted publishing via GitHub Actions)
- [x] Docs: a short "why not just NFKC?" section with examples (docs/why-not-nfkc.md)
