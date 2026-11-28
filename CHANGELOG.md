# Changelog

## 0.4.0 — 2026-11-28

Batch 4: richer classification labels, reading our own exports back in,
Japan Search as an opt-in source, and credit lines in the bibliography
formats.

### Added

- **C-code labels:** `decode_ccode()` / `Book.ccode_info` turn a Japanese
  C-code into 販売対象 / 発行形態 / 内容 (and 内容細目). CLI: `hondana ccode`.
  Table from the Japan ISBN Agency 利用の手引き 2025 (p. 24).
- **NDC ten classes:** `ndc_class()` / `Book.ndc_info` label an NDC mark
  with its main class only (0 総記 … 9 文学). CLI: `hondana ndc`. The
  finer NDC schedules are not bundled (copyright of the Japan Library
  Association).
- **`Book.cover`:** the cover URL already returned by openBD (and others)
  is now documented and tested. The image is never downloaded.
- **Import / convert:** `from_bibtex` / `from_ris` / `from_csl` and
  `loads()` read back the files hondana writes. CLI: `hondana convert`.
  `dumps(loads(text))` is a stable round trip.
- **Japan Search:** opt-in source for `search(sources=(…, "jpsearch"))`
  and `lookup(isbn, order=(…, "jpsearch"))` (exact ISBN match via SPARQL).
  Each database's terms are applied first; records keep `licence` and a
  出典 credit line (`Book.attribution`). See `docs/japan-search.md`.
- **ISBN registration-group names:** `registration_group()` and
  `hondana isbn --group` print the group name from the official
  RangeMessage table we already ship (`group` / `group_name` in `--json`).
- **Export credits:** BibTeX, RIS and CSL-JSON now carry the Japan Search
  metadata licence and 出典 line when present:
  - BibTeX: `copyright` (licence), `note` (credit line)
  - RIS: `N1` for the credit line, plus an `N1` line `Licence: …`
  - CSL-JSON: `license`, `note`

  These fields describe the *metadata*, not the book's own copyright.
  Records without a credit line export exactly as in 0.3.0. `loads()`
  reads them back.

### Fixed

- BibTeX escaping of backslash, tilde and caret ran in more than one pass,
  so a backslash came out as "\{\}" in LaTeX. Specials are now replaced in a single pass.

Install: `pip install hondana-ja==0.4.0`.
