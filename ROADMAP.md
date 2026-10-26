# Roadmap

Small steps, roughly one per day. Tick them off as they land.

- [x] Add GitHub Actions CI (Python 3.9–3.14, Windows)
- [x] Add 20 more kyujitai → shinjitai pairs (with tests)
- [x] Add 20 more simplified → shinjitai pairs, keep the "different character" exclusion list documented
- [x] `fold()`: option to fold small kana (ぁ→あ, っ→つ) for fuzzy matching
- [x] `fold()`: fold iteration marks (々 ゝ ゞ) — expand or drop, configurable
- [ ] Handle voiced/semi-voiced combining marks (U+3099/U+309A) explicitly, with tests
- [ ] ISBN: hyphenate ISBN-13 by registration group (start with 978-4 Japan)
- [ ] ISBN: `find_isbns()` should also catch "ISBN-10:" / "ISBN978…" without spaces
- [ ] Lookup: optional simple in-memory TTL cache wrapper for `fetch`
- [ ] Lookup: per-source timeout overrides
- [ ] Lookup: return the raw source payload behind a flag for debugging
- [ ] Lookup: add CiNii Books as an optional source
- [ ] CLI: `hondana fold --explain` showing each step's output
- [ ] Type hints pass `mypy --strict`
- [ ] Publish to PyPI (trusted publishing via GitHub Actions)
- [ ] Docs: a short "why not just NFKC?" section with examples
