"""ISBN lookup with source fallback: openBD → NDL Search → Google Books → Open Library.

Each source is tried on its own; one timing out never skips the rest. No
third-party dependencies — pass your own ``fetch`` to use httpx/requests,
add caching, or stub the network in tests.
"""
from __future__ import annotations

import html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable, Iterable, Optional

from .isbn import to_isbn13

__all__ = ["Book", "lookup", "SOURCES", "Fetch", "urllib_fetch", "cached"]

# fetch(url, params, timeout) -> (status_code, body_text)
Fetch = Callable[[str, dict, float], "tuple[int, str]"]

USER_AGENT = "hondana (+https://github.com/Jasonin2099/hondana)"


def urllib_fetch(url: str, params: dict, timeout: float) -> "tuple[int, str]":
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
    store: "dict[tuple, tuple[float, tuple[int, str]]]" = {}
    lock = threading.Lock()

    def wrapped(url: str, params: dict, timeout: float) -> "tuple[int, str]":
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

    def __bool__(self) -> bool:
        return bool(self.title)

    def to_dict(self) -> dict:
        return asdict(self)


def _https(u: str) -> str:
    return u.replace("http://", "https://", 1) if u else ""


def _openbd(isbn: str, fetch: Fetch) -> Optional[Book]:
    st, body = fetch("https://api.openbd.jp/v1/get", {"isbn": isbn}, 8)
    if st != 200:
        return None
    d = (json.loads(body or "null") or [None])[0]
    s = (d or {}).get("summary") or {}
    if not s.get("title"):
        return None
    return Book(isbn, s.get("title", ""), s.get("author", ""), s.get("publisher", ""), (s.get("pubdate") or "")[:4], _https(s.get("cover", "")), "openBD")


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


SOURCES: dict = {"openbd": _openbd, "ndl": _ndl, "google": _google, "openlibrary": _openlibrary}
DEFAULT_ORDER = ("openbd", "ndl", "google", "openlibrary")


def lookup(
    raw_isbn: str,
    *,
    fetch: Fetch = urllib_fetch,
    order: Iterable[str] = DEFAULT_ORDER,
    on_error: Optional[Callable[[str, BaseException], None]] = None,
) -> Optional[Book]:
    """Look an ISBN up. Returns ``None`` for an invalid ISBN or when no source knows it."""
    isbn = to_isbn13(raw_isbn, strict=True)
    if not isbn:
        return None
    for name in order:
        try:
            b = SOURCES[name](isbn, fetch)
        except Exception as e:  # network, JSON, anything: next source
            if on_error:
                on_error(name, e)
            continue
        if b:
            return b
    return None
