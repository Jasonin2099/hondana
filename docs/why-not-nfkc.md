# Why not just NFKC?

`unicodedata.normalize("NFKC", s)` is the usual first answer for "make these two
strings compare equal". It is also hondana's first step (`width`). On its own it
misses most of what goes wrong with Japanese book titles:

| user typed | catalogue has | NFKC equal? | `fold()` equal? | why |
|---|---|---|---|---|
| `圖書館` | `図書館` | no | yes | Kyujitai vs shinjitai are different code points, not compatibility variants. |
| `图书馆` | `図書館` | no | yes | Simplified Chinese → shinjitai is a table, not a Unicode rule. |
| `ハリー・ポッター` | `はりー ぽったー` | no | yes | Katakana vs hiragana, the long-vowel mark, the middle dot and spaces. |
| `ﾊﾘｰ ﾎﾟｯﾀｰ` | `ハリー・ポッター` | no | yes | NFKC fixes the half-width kana but not the `・` vs space. |
| `ＡＢＣ` | `abc` | no | yes | NFKC makes it `ABC`; case is a separate step. |
| `か゛` | `が` | no | yes | NFKC turns the spacing `゛` into space + combining mark, which never joins `か`. |
| `時々` | `時時` | no | with `iteration_marks="expand"` | Iteration marks are ordinary characters to Unicode. |

Every row is checked in `tests/test_fold.py::test_why_not_nfkc`. To try it yourself:

```python
import unicodedata
from hondana import fold
unicodedata.normalize("NFKC", "圖書館") == unicodedata.normalize("NFKC", "図書館")  # False
fold("圖書館") == fold("図書館")                                                    # True
```

Things to know the other way round:

- `fold()` is a **matching key**, not display text. It drops `ー`, punctuation and
  case on purpose, so `コーヒー` and `コヒ` fold the same. Store the original, compare
  the folded.
- The character tables are a starter set. A simplified character that is a *different* character in
  Japanese (机 desk vs 機 machine) is left out on purpose; see `SIMP_EXCLUDED`
  in `src/hondana/_tables.py`.
- To see which step made two strings match or not:
  `python -m hondana fold --explain "ﾊﾘｰ・ﾎﾟｯﾀｰ"`.
