"""ISBN lookup with source fallback: openBD → NDL Search → Google Books → Open Library.

CiNii Books is available as an optional extra source (``order=(..., "cinii")``).

Each source is tried on its own; one timing out never skips the rest.
``lookup(..., merge=True)`` queries every source and fills missing fields;
``lookup_many()`` batches ISBNs with an optional ``rate`` limit.
``search()`` looks up a title or author (no ISBN) via NDL Search and
Open Library (Japan Search on request: ``sources=(..., "jpsearch")``,
see :mod:`hondana.jpsearch`), and ranks hits with ``fold()``. No third-party dependencies
— pass your own ``fetch`` to use httpx/requests, add caching, or stub
the network in tests.
"""
from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from .ccode import CCode, decode_ccode
from .ndc import NdcClass, ndc_class
from .isbn import to_isbn13
from .fold import fold

__all__ = ["Book", "lookup", "lookup_many", "search", "SOURCES", "Fetch", "urllib_fetch", "cached"]

# fetch(url, params, timeout) -> (status_code, body_text)
Fetch = Callable[[str, Dict[str, Any], float], Tuple[int, str]]
Source = Callable[[str, Fetch], "Optional[Book]"]

USER_AGENT = "hondana (+https://github.com/Jasonin2099/hondana)"


def urllib_fetch(url: str, params: "dict[str, Any]", timeout: float) -> "tuple[int, str]":
    q = url + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(q, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


def cached(
    fetch: Fetch = urllib_fetch,
    *,
    ttl: float = 3600,
    maxsize: int = 512,
    clock: Callable[[], float] = time.monotonic,
) -> Fetch:
    """Wrap ``fetch`` with a small in-memory TTL cache.

    Only ``200`` and ``404`` answers are kept (a book that isn't there is worth
    remembering too); errors and other statuses always go to the network again.
    When full, the entry closest to expiry is dropped. Safe to share between threads.

        lookup(isbn, fetch=cached(ttl=600))
    """
    store: "dict[tuple[str, tuple[tuple[str, str], ...]], tuple[float, tuple[int, str]]]" = {}
    lock = threading.Lock()

    def wrapped(url: str, params: "dict[str, Any]", timeout: float) -> "tuple[int, str]":
        key = (url, tuple(sorted((str(k), str(v)) for k, v in (params or {}).items())))
        now = clock()
        with lock:
            hit = store.get(key)
            if hit and hit[0] > now:
                return hit[1]
        res = fetch(url, params, timeout)
        if res[0] in (200, 404):
            with lock:
                if len(store) >= maxsize and key not in store:
                    for k in [k for k, (exp, _) in store.items() if exp <= now] or [min(store, key=lambda k: store[k][0])]:
                        del store[k]
                store[key] = (now + ttl, res)
        return res

    return wrapped


@dataclass
class Book:
    isbn: str
    title: str = ""
    author: str = ""
    publisher: str = ""
    year: str = ""
    cover: str = ""
    source: str = ""
    #: Japanese C-code (4 digits, no leading ``C``), from openBD when present.
    ccode: str = ""
    #: NDC class mark, from openBD ``hanmoto.ndccode`` when present.
    ndc: str = ""
    #: The source's response body, only filled in by ``lookup(..., raw=True)``.
    raw: Optional[str] = field(default=None, repr=False, compare=False)
    #: Licence of the metadata when the source states one per record
    #: (Japan Search: ``cc0``, ``cc-by``, …); empty for the other sources.
    licence: str = ""
    #: Credit line to show with this record when the source asks for one
    #: (Japan Search, see :func:`hondana.jpsearch.attribution`).
    attribution: str = ""

    def __bool__(self) -> bool:
        return bool(self.title)

    @property
    def ccode_info(self) -> Optional[CCode]:
        """``ccode`` decoded into 販売対象 / 発行形態 / 内容 labels, or ``None``."""
        return decode_ccode(self.ccode)

    @property
    def ndc_info(self) -> Optional[NdcClass]:
        """``ndc`` with the label of its main class (0 総記 … 9 文学), or ``None``."""
        return ndc_class(self.ndc)

    def to_dict(self) -> Dict[str, Any]:
        """Fields as a dict. When ``ccode`` decodes, ``ccode_labels`` holds the
        audience / form / subject / detail labels; when ``ndc`` parses,
        ``ndc_class`` holds its main class and labels (neither is part of the
        dataclass). ``licence`` and ``attribution`` appear only when set."""
        d: Dict[str, Any] = asdict(self)
        if d["raw"] is None:
            del d["raw"]
        for k in ("licence", "attribution"):
            if not d[k]:
                del d[k]
        info = self.ccode_info
        if info is not None:
            d["ccode_labels"] = {k: v for k, v in info._asdict().items() if k != "code"}
        ndc = self.ndc_info
        if ndc is not None:
            d["ndc_class"] = {"main": ndc.main, "label": ndc.label, "label_en": ndc.label_en}
        return d

    def to_bibtex(self) -> str:
        from .export import to_bibtex
        return to_bibtex(self)

    def to_ris(self) -> str:
        from .export import to_ris
        return to_ris(self)

    def to_csl(self) -> Dict[str, Any]:
        from .export import to_csl
        return to_csl(self)


def _https(u: str) -> str:
    return u.replace("http://", "https://", 1) if u else ""


def _as_list(v: Any) -> list[Any]:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _openbd_classifiers(payload: "dict[str, Any]") -> "tuple[str, str]":
    """Return ``(ccode, ndc)`` from an openBD record.

    C-code is ONIX subject scheme 78 (Japanese book trade C-Code), with
    ``hanmoto.ccode`` as a fallback. NDC is ``hanmoto.ndccode`` (not ONIX
    scheme 79, which is the bookseller genre code). A leading ``C`` on the
    C-code, if present, is dropped.
    """
    ccode = ""
    subjects = ((payload.get("onix") or {}).get("DescriptiveDetail") or {}).get("Subject")
    for s in _as_list(subjects):
        if not isinstance(s, dict):
            continue
        scheme = str(s.get("SubjectSchemeIdentifier") or "").strip()
        code = str(s.get("SubjectCode") or "").strip()
        if scheme == "78" and code and not ccode:
            ccode = code[1:] if code[:1] in "CcＣｃ" else code
    han = payload.get("hanmoto") or {}
    ndc = ""
    if isinstance(han, dict):
        ndc = str(han.get("ndccode") or han.get("ndc") or "").strip()
        if not ccode:
            raw = str(han.get("ccode") or han.get("c_code") or "").strip()
            if raw:
                ccode = raw[1:] if raw[:1] in "CcＣｃ" else raw
    return ccode, ndc


def _openbd(isbn: str, fetch: Fetch) -> Optional[Book]:
    st, body = fetch("https://api.openbd.jp/v1/get", {"isbn": isbn}, 8)
    if st != 200:
        return None
    d = (json.loads(body or "null") or [None])[0]
    if not d:
        return None
    s = d.get("summary") or {}
    if not s.get("title"):
        return None
    ccode, ndc = _openbd_classifiers(d)
    return Book(
        isbn, s.get("title", ""), s.get("author", ""), s.get("publisher", ""),
        (s.get("pubdate") or "")[:4], _https(s.get("cover", "")), "openBD",
        ccode=ccode, ndc=ndc,
    )


def _ndl(isbn: str, fetch: Fetch) -> Optional[Book]:
    st, body = fetch("https://ndlsearch.ndl.go.jp/api/opensearch", {"isbn": isbn, "cnt": 1}, 15)
    if st != 200 or "<item>" not in body:
        return None
    it = body.split("<item>", 1)[1]

    def g(tag: str) -> str:
        m = re.search(r"<%s[^>]*>([^<]+)</%s>" % (tag, tag), it)
        return html.unescape(m.group(1)).strip() if m else ""

    title = g("title")
    if not title:
        return None
    year = (re.search(r"\d{4}", g("dcterms:issued")) or [""])[0] if g("dcterms:issued") else ""
    return Book(isbn, title, g("dc:creator"), g("dc:publisher"), year, "", "NDL")


def _google(isbn: str, fetch: Fetch) -> Optional[Book]:
    st, body = fetch("https://www.googleapis.com/books/v1/volumes", {"q": "isbn:" + isbn}, 8)
    if st != 200:
        return None
    v = ((json.loads(body or "{}").get("items") or [{}])[0].get("volumeInfo")) or {}
    if not v.get("title"):
        return None
    title = v["title"] + ("：" + v["subtitle"] if v.get("subtitle") else "")
    cover = _https(((v.get("imageLinks") or {}).get("thumbnail") or "")).replace("&edge=curl", "")
    return Book(isbn, title, "、".join(v.get("authors") or []), v.get("publisher", ""), (v.get("publishedDate") or "")[:4], cover, "Google Books")


def _openlibrary(isbn: str, fetch: Fetch) -> Optional[Book]:
    st, body = fetch("https://openlibrary.org/api/books", {"bibkeys": "ISBN:" + isbn, "format": "json", "jscmd": "data"}, 8)
    if st != 200:
        return None
    v = json.loads(body or "{}").get("ISBN:" + isbn)
    if not v or not v.get("title"):
        return None
    title = v["title"] + (": " + v["subtitle"] if v.get("subtitle") else "")
    year = re.sub(r"\D", "", v.get("publish_date") or "")[-4:]
    return Book(
        isbn, title, "、".join(a.get("name", "") for a in v.get("authors") or []),
        "、".join(p.get("name", "") for p in v.get("publishers") or []), year,
        (v.get("cover") or {}).get("medium", ""), "Open Library",
    )


def _first(v: Any) -> str:
    if isinstance(v, list):
        v = v[0] if v else ""
    if isinstance(v, dict):
        v = v.get("@value") or v.get("@id") or ""
    return str(v or "").strip()


def _cinii(isbn: str, fetch: Fetch) -> Optional[Book]:
    """CiNii Books (university library holdings). Optional: not in the default order.

    CiNii asks callers to register an application ID; set ``HONDANA_CINII_APPID``
    to send one. Enable with ``lookup(isbn, order=(..., "cinii"))``.
    """
    params: "dict[str, Any]" = {"isbn": isbn, "format": "json", "count": 1}
    appid = os.environ.get("HONDANA_CINII_APPID", "")
    if appid:
        params["appid"] = appid
    st, body = fetch("https://ci.nii.ac.jp/books/opensearch/search", params, 10)
    if st != 200:
        return None
    graph = json.loads(body or "{}").get("@graph") or [{}]
    items = (graph[0] or {}).get("items") or []
    if not items:
        return None
    it = items[0]
    title = _first(it.get("title"))
    if not title:
        return None
    year = (re.search(r"\d{4}", _first(it.get("dc:date"))) or [""])[0]
    return Book(isbn, title, _first(it.get("dc:creator")), _first(it.get("dc:publisher")), year, "", "CiNii Books")


SOURCES: "dict[str, Source]" = {"openbd": _openbd, "ndl": _ndl, "google": _google, "openlibrary": _openlibrary, "cinii": _cinii}
DEFAULT_ORDER = ("openbd", "ndl", "google", "openlibrary")


def _with_timeout(fetch: Fetch, timeout: float) -> Fetch:
    return lambda url, params, _ignored: fetch(url, params, timeout)


def _recording(fetch: Fetch, sink: "list[str]") -> Fetch:
    def f(url: str, params: "dict[str, Any]", timeout: float) -> "tuple[int, str]":
        res = fetch(url, params, timeout)
        sink.append(res[1])
        return res

    return f


_MERGE_FIELDS = ("title", "author", "publisher", "year", "cover", "ccode", "ndc")


def _merge_books(books: "list[Book]") -> Book:
    """Build one Book by preferring the first non-empty value for each field.

    Sources that contributed at least one field are joined with ``+``
    (e.g. ``"openBD+NDL"``). ``raw`` keeps the first non-``None`` body.
    """
    out = Book(isbn=books[0].isbn)
    contributors: "list[str]" = []
    for b in books:
        used = False
        for f in _MERGE_FIELDS:
            if not getattr(out, f) and getattr(b, f):
                setattr(out, f, getattr(b, f))
                used = True
        if used and b.source and b.source not in contributors:
            contributors.append(b.source)
        if used and b.attribution and not out.attribution:
            # a field came from a source that asks for credit: keep its line
            out.licence, out.attribution = b.licence, b.attribution
        if out.raw is None and b.raw is not None:
            out.raw = b.raw
    out.source = "+".join(contributors)
    return out


def lookup(
    raw_isbn: str,
    *,
    fetch: Fetch = urllib_fetch,
    order: Iterable[str] = DEFAULT_ORDER,
    on_error: Optional[Callable[[str, BaseException], None]] = None,
    timeouts: Optional["dict[str, float]"] = None,
    raw: bool = False,
    merge: bool = False,
    jpsearch_policy: Optional[Any] = None,
    on_skip: Optional[Callable[[str, str], None]] = None,
) -> Optional[Book]:
    """Look an ISBN up. Returns ``None`` for an invalid ISBN or when no source knows it.

    ``timeouts`` overrides the per-request timeout of some sources, in seconds
    (defaults: NDL 15, CiNii 10, the others 8), e.g. ``timeouts={"ndl": 30}``.

    ``raw=True`` keeps the winning source's response body on ``Book.raw``, for
    debugging a field that came out wrong. It is left out of ``to_dict()`` otherwise.
    With ``merge=True``, ``raw`` keeps the first successful source's body.

    ``merge=True`` queries every source in ``order`` and fills missing fields from
    later ones (first non-empty wins per field). Default ``False`` keeps the
    first-wins behaviour.

    ``"jpsearch"`` (Japan Search) is opt-in: ``order=(..., "jpsearch")``.
    It matches the ISBN exactly through the SPARQL endpoint, applies each
    database's terms (``jpsearch_policy``, ``on_skip`` as in :func:`search`)
    and fills ``Book.licence`` / ``Book.attribution``; with ``merge=True``
    the credit line is kept when one of its fields was used.
    """
    isbn = to_isbn13(raw_isbn, strict=True)
    if not isbn:
        return None
    unknown = set(timeouts or ()) - set(SOURCES) - {"jpsearch"}
    if unknown:
        raise ValueError(f"unknown source(s) in timeouts: {', '.join(sorted(unknown))}")
    found: "list[Book]" = []
    for name in order:
        f = fetch if not timeouts or name not in timeouts else _with_timeout(fetch, timeouts[name])
        last: "list[str]" = []
        if raw:
            f = _recording(f, last)
        try:
            if name == "jpsearch":
                b = _jpsearch_lookup(isbn, f, jpsearch_policy, on_skip, raw)
            else:
                b = SOURCES[name](isbn, f)
        except Exception as e:  # network, JSON, anything: next source
            if on_error:
                on_error(name, e)
            continue
        if b:
            if raw and last and b.raw is None:
                b.raw = last[-1]
            if not merge:
                return b
            found.append(b)
    if not found:
        return None
    return _merge_books(found) if merge else None


def lookup_many(
    isbns: Iterable[str],
    *,
    fetch: Fetch = urllib_fetch,
    order: Iterable[str] = DEFAULT_ORDER,
    on_error: Optional[Callable[[str, BaseException], None]] = None,
    timeouts: Optional["dict[str, float]"] = None,
    raw: bool = False,
    merge: bool = False,
    rate: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
    jpsearch_policy: Optional[Any] = None,
    on_skip: Optional[Callable[[str, str], None]] = None,
) -> "list[Optional[Book]]":
    """Look up many ISBNs; one ``Book|None`` per input, preserving order.

    ``rate`` is the minimum seconds between successive lookups (``0`` = no delay).
    ``sleep`` is injectable for tests. All other kwargs are forwarded to ``lookup``.
    """
    order_t = tuple(order)
    out: "list[Optional[Book]]" = []
    for i, raw_isbn in enumerate(isbns):
        if i and rate > 0:
            sleep(rate)
        out.append(
            lookup(
                raw_isbn,
                fetch=fetch,
                order=order_t,
                on_error=on_error,
                timeouts=timeouts,
                raw=raw,
                merge=merge,
                jpsearch_policy=jpsearch_policy,
                on_skip=on_skip,
            )
        )
    return out


def _xml_tag(item: str, tag: str) -> str:
    m = re.search(r"<%s[^>]*>([^<]+)</%s>" % (tag, tag), item)
    return html.unescape(m.group(1)).strip() if m else ""


def _ndl_isbn(item: str) -> str:
    found: list[str] = []
    for m in re.finditer(r"<dc:identifier[^>]*>([^<]+)</dc:identifier>", item, re.I):
        found.append(html.unescape(m.group(1)))
    for raw in found:
        # "ISBN 978-4-00-310101-8" or a bare number
        for token in re.findall(r"97[89][\d\- ]{10,16}|\b\d{9}[\dXx]\b", raw):
            isbn = to_isbn13(token, strict=True)
            if isbn:
                return isbn
    return ""


def _book_from_ndl_item(item: str) -> Optional[Book]:
    title = _xml_tag(item, "title")
    if not title:
        return None
    issued = _xml_tag(item, "dcterms:issued")
    year = (re.search(r"\d{4}", issued) or [""])[0] if issued else ""
    return Book(
        _ndl_isbn(item),
        title,
        _xml_tag(item, "dc:creator"),
        _xml_tag(item, "dc:publisher"),
        year,
        "",
        "NDL",
    )


def _ndl_search(query: str, title: str, author: str, fetch: Fetch, limit: int) -> list[Book]:
    params: dict[str, Any] = {"cnt": max(1, min(int(limit), 50))}
    if query:
        params["any"] = query
    else:
        if title:
            params["title"] = title
        if author:
            params["creator"] = author
    st, body = fetch("https://ndlsearch.ndl.go.jp/api/opensearch", params, 15)
    if st != 200 or "<item>" not in (body or ""):
        return []
    out: list[Book] = []
    for chunk in body.split("<item>")[1:]:
        b = _book_from_ndl_item(chunk)
        if b:
            out.append(b)
        if len(out) >= limit:
            break
    return out


def _ol_search(query: str, title: str, author: str, fetch: Fetch, limit: int) -> list[Book]:
    params: dict[str, Any] = {"limit": max(1, min(int(limit), 50))}
    if query:
        params["q"] = query
    else:
        if title:
            params["title"] = title
        if author:
            params["author"] = author
    st, body = fetch("https://openlibrary.org/search.json", params, 8)
    if st != 200:
        return []
    docs = json.loads(body or "{}").get("docs") or []
    out: list[Book] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        name = str(doc.get("title") or "")
        subtitle = str(doc.get("subtitle") or "")
        if subtitle:
            name = name + (": " if name else "") + subtitle
        if not name:
            continue
        isbn = ""
        for raw in doc.get("isbn") or []:
            isbn = to_isbn13(str(raw), strict=True)
            if isbn:
                break
        cover = ""
        if doc.get("cover_i"):
            cover = "https://covers.openlibrary.org/b/id/%s-M.jpg" % doc["cover_i"]
        year = str(doc.get("first_publish_year") or "")
        year = year[:4] if year else ""
        authors = "、".join(str(a) for a in (doc.get("author_name") or []) if a)
        pubs = doc.get("publisher") or []
        publisher = str(pubs[0]) if pubs else ""
        out.append(Book(isbn, name, authors, publisher, year, cover, "Open Library"))
        if len(out) >= limit:
            break
    return out


def _jpsearch_lookup(
    isbn: str, fetch: Fetch, policy: Any, on_skip: Optional[Callable[[str, str], None]], raw: bool = False
) -> Optional[Book]:
    """``lookup()`` source for Japan Search: the first record that passes the policy."""
    from .jpsearch import JapanSearch, Policy

    client = JapanSearch(fetch, policy if policy is not None else Policy(), on_skip=on_skip)
    recs = client.lookup(isbn, limit=1, raw=raw)
    if not recs:
        return None
    b = recs[0].to_book()
    if raw and recs[0].raw is not None:
        b.raw = json.dumps(recs[0].raw, ensure_ascii=False)
    return b


def _jpsearch_source(policy: Any, on_skip: Optional[Callable[[str, str], None]], raw: bool) -> Any:
    """``search()`` source for Japan Search (imported lazily: optional)."""
    from .jpsearch import JapanSearch, Policy

    def run(query: str, title: str, author: str, fetch: Fetch, limit: int) -> "list[Book]":
        client = JapanSearch(fetch, policy if policy is not None else Policy(), on_skip=on_skip)
        out = []
        for rec in client.search(query, title=title, author=author, limit=limit, raw=raw):
            b = rec.to_book()
            if raw and rec.raw is not None:
                b.raw = json.dumps(rec.raw, ensure_ascii=False)
            out.append(b)
        return out

    return run


_SEARCH_SOURCES: dict[str, Any] = {"ndl": _ndl_search, "openlibrary": _ol_search}
DEFAULT_SEARCH_SOURCES = ("ndl", "openlibrary")


def _search_rank(book: Book, query: str, title: str, author: str) -> tuple[int, int, str]:
    q = fold(query or title)
    want_author = fold(author)
    ft = fold(book.title)
    fa = fold(book.author)
    if q and ft == q:
        tscore = 0
    elif q and ft.startswith(q):
        tscore = 1
    elif q and q in ft:
        tscore = 2
    elif q:
        tscore = 3
    else:
        tscore = 1
    if want_author:
        ascore = 0 if (want_author == fa or want_author in fa or (fa and fa in want_author)) else 1
    else:
        ascore = 0
    return (tscore, ascore, book.title)


def _search_merge_key(book: Book) -> tuple[str, ...]:
    if book.isbn:
        return ("isbn", book.isbn)
    title, author = fold(book.title), fold(book.author)
    if title or author:
        return ("text", title, author)
    return ("empty", book.source, book.title)


def search(
    query: str = "",
    *,
    title: str = "",
    author: str = "",
    fetch: Fetch = urllib_fetch,
    sources: Iterable[str] = DEFAULT_SEARCH_SOURCES,
    limit: int = 10,
    timeouts: Optional["dict[str, float]"] = None,
    on_error: Optional[Callable[[str, BaseException], None]] = None,
    raw: bool = False,
    jpsearch_policy: Optional[Any] = None,
    on_skip: Optional[Callable[[str, str], None]] = None,
) -> "list[Book]":
    """Search by title or author, without an ISBN.

    Queries NDL Search and Open Library (override with ``sources``), then
    ranks hits with :func:`hondana.fold` so typographic variants of the
    same title float to the top. Pass at least one of ``query``, ``title``
    or ``author``. ``limit`` caps the result list (per source, then again
    after merging). ``fetch``, ``timeouts``, ``on_error`` and ``raw``
    behave as in :func:`lookup`.

    ``"jpsearch"`` (Japan Search) is an opt-in source:
    ``sources=("ndl", "openlibrary", "jpsearch")``. Each database's terms
    are applied first (see :mod:`hondana.jpsearch`; ``jpsearch_policy`` is a
    :class:`hondana.jpsearch.Policy`, default ``Policy()``), and its books
    carry ``licence`` and ``attribution`` — show the credit line wherever
    you show the record. ``on_skip(database_id, reason)`` reports the Japan
    Search databases left out. A book found by an earlier source (same
    ISBN or same folded title + author) is kept from that source.
    """
    query, title, author = (query or "").strip(), (title or "").strip(), (author or "").strip()
    if not (query or title or author):
        raise ValueError("search needs a query, title or author")
    sources = tuple(sources)
    unknown = set(timeouts or ()) - set(_SEARCH_SOURCES) - {"jpsearch"}
    if unknown:
        raise ValueError(f"unknown source(s) in timeouts: {', '.join(sorted(unknown))}")
    found: list[Book] = []
    seen: set[tuple[str, ...]] = set()
    for name in sources:
        if name not in _SEARCH_SOURCES and name != "jpsearch":
            raise ValueError(f"unknown search source: {name}")
    for name in sources:
        fn = _SEARCH_SOURCES.get(name) or _jpsearch_source(jpsearch_policy, on_skip, raw)
        f = fetch if not timeouts or name not in timeouts else _with_timeout(fetch, timeouts[name])
        last: list[str] = []
        if raw:
            f = _recording(f, last)
        try:
            hits = fn(query, title, author, f, limit)
        except Exception as e:  # network, JSON, anything: next source
            if on_error:
                on_error(name, e)
            continue
        for i, b in enumerate(hits):
            if raw and last and i == 0 and b.raw is None:
                b.raw = last[-1]
            key = _search_merge_key(b)
            if key in seen:
                continue
            seen.add(key)
            found.append(b)
    found.sort(key=lambda b: _search_rank(b, query, title, author))
    return found[: max(1, int(limit))]
