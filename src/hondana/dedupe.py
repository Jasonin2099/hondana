"""De-duplicate a list of books by ISBN or folded title + author."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .fold import fold
from .isbn import to_isbn13

__all__ = ["DuplicateGroup", "DedupeResult", "dedupe", "dedupe_key", "resolve_field"]

Row = Mapping[str, Any]
Key = Tuple[str, ...]

_ISBN_ALIASES = ("isbn", "isbn13", "isbn-13", "isbn_13", "isbn10", "isbn-10", "isbn_10")
_TITLE_ALIASES = ("title", "書名", "题名", "題名", "タイトル", "標題")
_AUTHOR_ALIASES = ("author", "authors", "著者", "作者", "編者", "编者")


def _norm(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def resolve_field(rows: Sequence[Row], aliases: Sequence[str], explicit: Optional[str]) -> Optional[str]:
    """Return the column name to use, or None when nothing matches."""
    if not rows:
        return explicit
    keys = list(rows[0].keys())
    if explicit:
        if explicit in keys:
            return explicit
        target = _norm(explicit)
        for k in keys:
            if _norm(k) == target:
                return k
        raise KeyError(f"column {explicit!r} not in CSV (have {', '.join(keys)})")
    lowered = {_norm(k): k for k in keys}
    for alias in aliases:
        if alias in keys:
            return alias
        if _norm(alias) in lowered:
            return lowered[_norm(alias)]
    return None


def _cell(row: Row, name: Optional[str]) -> str:
    if not name:
        return ""
    v = row.get(name, "")
    return "" if v is None else str(v).strip()


def dedupe_key(
    row: Row,
    *,
    isbn_field: Optional[str] = "isbn",
    title_field: Optional[str] = "title",
    author_field: Optional[str] = "author",
    **fold_opts: Any,
) -> Key:
    """Return a grouping key for one row.

    A valid ISBN (strict check digit) becomes ``("isbn", isbn13)``.
    Otherwise the key is ``("text", folded_title, folded_author)``.
    An empty text key is ``("empty",)`` so blank rows do not merge.
    """
    isbn = to_isbn13(_cell(row, isbn_field), strict=True)
    if isbn:
        return ("isbn", isbn)
    title = fold(_cell(row, title_field), **fold_opts)
    author = fold(_cell(row, author_field), **fold_opts)
    if title or author:
        return ("text", title, author)
    return ("empty",)


@dataclass
class DuplicateGroup:
    """Rows that refer to the same book, in input order."""
    kind: str
    key: Key
    rows: List[Row] = field(default_factory=list)
    indexes: List[int] = field(default_factory=list)

    @property
    def extra(self) -> int:
        return max(0, len(self.rows) - 1)

    @property
    def isbn(self) -> str:
        return self.key[1] if self.kind == "isbn" and len(self.key) > 1 else ""


@dataclass
class DedupeResult:
    """Outcome of :func:`dedupe`. ``unique`` keeps the first row of each group."""
    groups: List[DuplicateGroup] = field(default_factory=list)

    @property
    def unique(self) -> List[Row]:
        return [g.rows[0] for g in self.groups]

    @property
    def duplicate_groups(self) -> List[DuplicateGroup]:
        return [g for g in self.groups if len(g.rows) > 1]

    @property
    def extra(self) -> int:
        return sum(g.extra for g in self.groups)

    def __len__(self) -> int:
        return len(self.groups)


class _DSU:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, i: int) -> int:
        p = self.parent
        while p[i] != i:
            p[i] = p[p[i]]
            i = p[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def dedupe(
    rows: Iterable[Row],
    *,
    isbn_field: Optional[str] = None,
    title_field: Optional[str] = None,
    author_field: Optional[str] = None,
    **fold_opts: Any,
) -> DedupeResult:
    """Group rows that share a valid ISBN *or* the same folded title + author.

    Two rows also end up in the same group when a third row bridges them
    (one side matched by ISBN, the other by title + author). Blank rows
    with no ISBN stay in their own group and are never merged. The first
    spelling of each group is preserved in :attr:`DedupeResult.unique`.

    Column names are detected from common aliases (``isbn`` / ``書名`` /
    ``著者`` …) when not given explicitly.
    """
    materialised: List[Row] = list(rows)
    isbn_field = resolve_field(materialised, _ISBN_ALIASES, isbn_field)
    title_field = resolve_field(materialised, _TITLE_ALIASES, title_field)
    author_field = resolve_field(materialised, _AUTHOR_ALIASES, author_field)

    n = len(materialised)
    dsu = _DSU(n)
    by_isbn: Dict[str, int] = {}
    by_text: Dict[Tuple[str, str], int] = {}
    kinds: List[str] = []
    keys: List[Key] = []

    for i, row in enumerate(materialised):
        isbn = to_isbn13(_cell(row, isbn_field), strict=True)
        title = fold(_cell(row, title_field), **fold_opts)
        author = fold(_cell(row, author_field), **fold_opts)
        text: Optional[Tuple[str, str]] = (title, author) if (title or author) else None
        if isbn:
            kinds.append("isbn")
            keys.append(("isbn", isbn))
            prev = by_isbn.get(isbn)
            if prev is None:
                by_isbn[isbn] = i
            else:
                dsu.union(prev, i)
        elif text:
            kinds.append("text")
            keys.append(("text", text[0], text[1]))
        else:
            kinds.append("empty")
            keys.append(("empty", str(i)))  # unique per blank row
        if isbn and text:
            prev_t = by_text.get(text)
            if prev_t is None:
                by_text[text] = i
            else:
                dsu.union(prev_t, i)
        elif text and not isbn:
            prev_t = by_text.get(text)
            if prev_t is None:
                by_text[text] = i
            else:
                dsu.union(prev_t, i)

    buckets: Dict[int, DuplicateGroup] = {}
    order: List[int] = []
    for i, row in enumerate(materialised):
        root = dsu.find(i)
        if root not in buckets:
            # Prefer an ISBN key if any member has one; else the first row's key.
            buckets[root] = DuplicateGroup(kind=kinds[root], key=keys[root])
            order.append(root)
        g = buckets[root]
        if kinds[i] == "isbn" and g.kind != "isbn":
            g.kind = "isbn"
            g.key = keys[i]
        g.rows.append(row)
        g.indexes.append(i)
    return DedupeResult(groups=[buckets[r] for r in order])
