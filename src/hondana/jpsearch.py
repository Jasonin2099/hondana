"""Japan Search (ジャパンサーチ) client that follows each database's terms.

Japan Search (https://jpsearch.go.jp/) aggregates metadata from 300+
databases run by libraries, museums and archives. Its simple Web API is
free and needs no key, but the conditions are set **per database**:

* ``apiType`` — ``ok`` (API allowed), ``restricted`` (一部項目利用不可: some
  fields may not be used through the API) or ``ng`` (API利用不可).
* ``metadataRights`` — free text. Empty means CC0 (site policy); otherwise
  CC BY, CC BY-NC-SA, 政府標準利用規約, "二次利用不可", a link to the
  holder's own terms, …
* The site policy asks users to credit the source even for CC0 data
  (「出典：ジャパンサーチ「…（…）」のメタデータ」).

This module reads those conditions from the API itself and applies a
:class:`Policy` before a record reaches you:

* ``ng`` databases and terms that forbid reuse are always skipped.
* ``restricted`` databases are skipped unless ``Policy(restricted=True)``;
  then the fields the database marks ``guionly`` are dropped.
* Only licences in ``Policy.accept`` pass (default: CC0, PDM, CC BY,
  PDL 1.0, 政府標準利用規約). Free-text terms, caveats ("ただし…",
  "…をご確認ください") and unknown databases are skipped unless you have
  read the terms and list the database in ``Policy.allow``.
* Every :class:`Record` carries its database's licence and a ready-made
  attribution line.

Only standard-library code; pass your own ``fetch`` as elsewhere in hondana.
Keyword search on an ISBN is fuzzy on Japan Search (it matches unrelated
records), so :meth:`JapanSearch.search` takes title / author and
:meth:`JapanSearch.lookup` finds an ISBN through the SPARQL endpoint,
matching the ``schema:identifier`` value exactly.

>>> classify_rights("<p>CC BY4.0 で利用できます。</p>")
('cc-by', False)
>>> classify_rights("")
('cc0', False)
>>> classify_rights("二次利用不可")
('no-reuse', False)
>>> classify_rights("CC BY-SA 、データベース利用規定をご確認ください。")
('cc-by-sa', True)
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional, Tuple

from .lookup import Book, Fetch, urllib_fetch
from .isbn import hyphenate, to_isbn10, to_isbn13

__all__ = [
    "API",
    "Database",
    "Policy",
    "Record",
    "JapanSearch",
    "classify_rights",
    "isbn_literals",
    "parse_database",
    "attribution",
    "DEFAULT_ACCEPT",
]

API = "https://jpsearch.go.jp/api"
SITE = "https://jpsearch.go.jp"
SPARQL = "https://jpsearch.go.jp/rdf/sparql/"

#: Licences accepted by default. All allow reuse (also commercial) with at
#: most an attribution duty. Add e.g. ``"cc-by-sa"`` or ``"cc-by-nc"`` to
#: ``Policy.accept`` if your use fits those terms.
DEFAULT_ACCEPT: FrozenSet[str] = frozenset({"cc0", "pdm", "cc-by", "pdl", "gov"})

# Licences whose text requires a credit line. (The site policy *asks* for one
# for CC0 / PDM too; that request is not a legal condition.)
_ATTRIBUTION_REQUIRED = frozenset(
    {"cc-by", "cc-by-sa", "cc-by-nd", "cc-by-nc", "cc-by-nc-sa", "cc-by-nc-nd", "pdl", "gov"}
)

_NO_REUSE = re.compile(r"二次利用不可|無断で?(?:の)?(?:複製|転載|転用|使用|利用)|お断り|(?<!改変)禁止")
_CAVEAT = re.compile(r"ただし|但し|※|著作権あり|ご確認|確認してください|異なります|参照")
_CC = re.compile(r"(?<![A-Za-z])CC\s*-?\s*BY(?:\s*-\s*(NC|SA|ND))?(?:\s*-\s*(SA|ND))?", re.I)


def _plain(text: str) -> str:
    """HTML → plain text, NFKC, whitespace collapsed."""
    t = re.sub(r"<[^>]+>", " ", text or "")
    t = unicodedata.normalize("NFKC", html.unescape(t))
    return re.sub(r"\s+", " ", t).strip()


def classify_rights(text: str) -> Tuple[str, bool]:
    """Classify a database's ``metadataRights`` text.

    Returns ``(licence, caveat)``. ``licence`` is one of ``cc0``, ``pdm``,
    ``cc-by``, ``cc-by-sa``, ``cc-by-nd``, ``cc-by-nc``, ``cc-by-nc-sa``,
    ``cc-by-nc-nd``, ``pdl`` (公共データ利用規約), ``gov`` (政府標準利用規約),
    ``no-reuse`` or ``custom`` (anything else: own terms, several licences,
    "教育目的の利用可", …). ``caveat`` is true when the text adds conditions
    next to a recognised licence ("ただし…", "利用規定をご確認ください").
    An empty text is CC0 (Japan Search site policy).
    """
    t = _plain(text)
    if not t:
        return "cc0", False
    if _NO_REUSE.search(t):
        return "no-reuse", False
    found = set()
    for m in _CC.finditer(t):
        parts = [p.lower() for p in m.groups() if p]
        found.add("-".join(["cc-by"] + parts))
    if re.search(r"Creative\s*Commons\s*表示\s*\d|クリエイティブ・?コモンズ\s*表示\s*\d", t, re.I) and not re.search(
        r"非営利|継承|改変禁止", t
    ):
        found.add("cc-by")
    if re.search(r"\bCC0\b|CC\s*ZERO|パブリック・?ドメイン提供", t, re.I):
        found.add("cc0")
    if re.search(r"\bPDM\b|Public\s*Domain\s*Mark|パブリック・?ドメイン・?マーク", t, re.I):
        found.add("pdm")
    if re.search(r"公共データ利用規約|\bPDL\s*1\.0", t):
        found.add("pdl")
    if "政府標準利用規約" in t:
        found.add("gov")
    if "cc-by" in found and found - {"cc-by"} <= {"gov", "pdl"}:
        # "CC BY(政府標準利用規約(第2.0版)準拠)": both are the same CC BY 4.0-compatible terms
        found = {"cc-by"}
    if len(found) != 1:
        return "custom", False
    return found.pop(), bool(_CAVEAT.search(t))


@dataclass(frozen=True)
class Database:
    """One Japan Search database (連携データベース) and its terms."""

    id: str
    name: str = ""
    name_en: str = ""
    #: Holding institution (所蔵機関) when the database gives a readable name.
    provider: str = ""
    #: ``ok`` / ``restricted`` / ``ng`` as reported by the API.
    api_type: str = ""
    #: Plain text of ``metadataRights`` (Japanese, English).
    rights: str = ""
    rights_en: str = ""
    licence: str = "custom"
    caveat: bool = False
    #: The rights text says no per-record notice is needed (e.g. NDL data).
    no_record_notice: bool = False

    @property
    def page_url(self) -> str:
        return f"{SITE}/database/{self.id}"

    @property
    def attribution_required(self) -> bool:
        return self.licence in _ATTRIBUTION_REQUIRED


def parse_database(d: Dict[str, Any]) -> Database:
    """Build a :class:`Database` from one ``/api/database/...`` JSON object."""
    name = d.get("name") or {}
    rights = d.get("metadataRights") or {}
    ja = _plain(rights.get("ja") or "")
    en = _plain(rights.get("en") or "")
    licence, caveat = classify_rights(rights.get("ja") or rights.get("en") or "")
    provider = str(d.get("provider") or "").strip()
    if re.fullmatch(r"[\x21-\x7e]*", provider):  # an internal id like "libyamagata", not a name
        provider = ""
    return Database(
        id=str(d.get("id") or ""),
        name=str(name.get("ja") or ""),
        name_en=str(name.get("en") or ""),
        provider=provider,
        api_type=str(d.get("apiType") or ""),
        rights=ja,
        rights_en=en,
        licence=licence,
        caveat=caveat,
        no_record_notice="個別のメタデータに表示を行う必要はありません" in ja,
    )


def isbn_literals(isbn: str) -> List[str]:
    """The ``schema:identifier`` spellings of an ISBN in Japan Search's RDF.

    >>> isbn_literals("4634342502")
    ['ISBN:9784634342507', 'ISBN:978-4-634-34250-7', 'ISBN:4634342502', 'ISBN:4-634-34250-2']
    >>> isbn_literals("not an isbn")
    []
    """
    isbn13 = to_isbn13(isbn, strict=True)
    if not isbn13:
        return []
    forms = [isbn13]
    h13 = hyphenate(isbn13)
    if h13:
        forms.append(h13)
    i10 = to_isbn10(isbn13)
    if i10:
        forms.append(i10)
        if h13:
            forms.append(h13[4:-1] + i10[-1])
    return ["ISBN:" + f for f in dict.fromkeys(forms)]


def attribution(db: Database, item_id: str = "", *, modified: bool = False, lang: str = "ja") -> str:
    """Credit line in the style of the Japan Search site policy (出典等の記載例).

    >>> d = Database("bibnl", "全国書誌", "Japanese National Bibliography", "国立国会図書館")
    >>> attribution(d)
    '出典：ジャパンサーチ「全国書誌（国立国会図書館）」のメタデータ（https://jpsearch.go.jp/database/bibnl）'
    >>> attribution(d, "bibnl-1", modified=True, lang="en")
    'Source: Japan Search, "Japanese National Bibliography (国立国会図書館)" metadata, modified (https://jpsearch.go.jp/item/bibnl-1)'
    """
    url = f"{SITE}/item/{item_id}" if item_id else db.page_url
    if lang == "en":
        name = db.name_en or db.name or db.id
        if db.provider:
            name += f" ({db.provider})"
        return f'Source: Japan Search, "{name}" metadata{", modified" if modified else ""} ({url})'
    name = db.name or db.id
    if db.provider:
        name += f"（{db.provider}）"
    return f"出典：ジャパンサーチ「{name}」のメタデータ{'を改変して利用' if modified else ''}（{url}）"


@dataclass(frozen=True)
class Policy:
    """Which databases may be used.

    ``accept``: licences that pass on their own. ``allow``: database ids whose
    terms you have read and accept (lets ``custom`` terms, caveats or other
    licences through; never ``ng`` or ``no-reuse``). ``deny``: ids to skip.
    ``restricted``: include 一部項目利用不可 databases, dropping their
    ``guionly`` fields.
    """

    accept: FrozenSet[str] = DEFAULT_ACCEPT
    allow: FrozenSet[str] = frozenset()
    deny: FrozenSet[str] = frozenset()
    restricted: bool = False

    def reason_to_skip(self, db: Optional[Database]) -> str:
        """``""`` when ``db`` may be used, otherwise a short reason.

        >>> Policy().reason_to_skip(Database("x", api_type="ng", licence="cc0"))
        'API use not allowed (apiType=ng)'
        >>> Policy().reason_to_skip(Database("x", api_type="ok", licence="cc-by-nc"))
        'licence cc-by-nc not in Policy.accept'
        >>> Policy(allow=frozenset({"x"})).reason_to_skip(Database("x", api_type="ok", licence="custom"))
        ''
        """
        if db is None:
            return "unknown database (terms not available)"
        if db.id in self.deny:
            return "denied by Policy.deny"
        if db.api_type == "ng":
            return "API use not allowed (apiType=ng)"
        if db.api_type not in ("ok", "restricted"):
            return f"unknown apiType {db.api_type!r}"
        if db.api_type == "restricted" and not self.restricted:
            return "some fields not usable via the API (apiType=restricted)"
        if db.licence == "no-reuse":
            return "terms forbid reuse"
        if db.id in self.allow:
            return ""
        if db.licence not in self.accept:
            return f"licence {db.licence} not in Policy.accept"
        if db.caveat:
            return "terms add conditions; read them and add the id to Policy.allow"
        return ""


@dataclass
class Record:
    """One Japan Search item that passed the :class:`Policy`."""

    id: str
    database: str
    title: str = ""
    author: str = ""
    publisher: str = ""
    year: str = ""
    isbn: str = ""
    #: The item's page in the source database.
    link: str = ""
    licence: str = ""
    attribution_required: bool = False
    #: Credit line for this record (see :func:`attribution`).
    attribution: str = ""
    #: Fields left out because the database marks them ``guionly``.
    dropped: Tuple[str, ...] = ()
    raw: Optional[Dict[str, Any]] = field(default=None, repr=False, compare=False)

    @property
    def url(self) -> str:
        return f"{SITE}/item/{self.id}"

    def to_book(self) -> Book:
        """As a :class:`hondana.Book` (``source="Japan Search"``), keeping
        ``licence`` and ``attribution``."""
        return Book(
            self.isbn, self.title, self.author, self.publisher, self.year, "", "Japan Search",
            licence=self.licence, attribution=self.attribution,
        )


def _year(values: Iterable[Any]) -> str:
    for v in values:
        m = re.search(r"(?<!\d)(\d{4})(?!\d)", unicodedata.normalize("NFKC", str(v or "")))
        if m:
            return m.group(1)
    return ""


def _strs(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        out: List[str] = []
        for x in v:
            out.extend(_strs(x))
        return out
    if isinstance(v, dict):
        return []
    s = str(v).strip()
    return [s] if s else []


def _agents(v: Any) -> List[str]:
    out: List[str] = []
    for a in v if isinstance(v, list) else [v]:
        if isinstance(a, dict):
            out.extend(_strs((a.get("foaf:Agent") or {}).get("foaf:name-s")))
    return out


# DC-NDL ISBN: "…ISBN-u" holds an iss.ndl.go.jp URI (bibnl search hits),
# "…ISBN-s" the printed form "4-634-34250-2" (dignl items).
_ISBN_KEYS = tuple("dcterms:identifier_rdf:datatype_http://ndl_go_jp/dcndl/terms/ISBN-" + t for t in "us")


def _dcndl(item: Dict[str, Any]) -> Dict[str, Any]:
    """The NDL (DC-NDL) block of bibnl / dignl style items, or ``{}``."""
    for k, v in item.items():
        if k.endswith("-rdf:RDF") and isinstance(v, dict):
            res = v.get("dcndl:BibResource")
            if isinstance(res, dict):
                return res
    return {}


def _record(item: Dict[str, Any], db: Database, blocked: FrozenSet[str]) -> Optional[Record]:
    common = item.get("common") or {}
    title = "" if "title" in blocked else str(common.get("title") or "").strip()
    if not title:
        return None
    contributors = [] if "contributor" in blocked else _strs(common.get("contributor"))
    year = "" if "temporal" in blocked else _year(reversed(_strs(common.get("temporal"))))
    author, publisher, isbn = "、".join(contributors), "", ""
    res = _dcndl(item)
    if res:  # NDL records: creator and publisher are separate fields
        creators = _strs(res.get("dc:creator-s"))
        publishers = _agents(res.get("dcterms:publisher"))
        if "contributor" not in blocked and (creators or publishers):
            author, publisher = "、".join(creators), "、".join(publishers)
        for raw in [v for k in _ISBN_KEYS for v in _strs(res.get(k))]:
            isbn = to_isbn13(raw.rsplit("/", 1)[-1], strict=True) or ""
            if isbn:
                break
    item_id = str(item.get("id") or common.get("id") or "")
    return Record(
        id=item_id,
        database=db.id,
        title=title,
        author=author,
        publisher=publisher,
        year=year,
        isbn=isbn,
        link="" if "linkUrl" in blocked else str(common.get("linkUrl") or ""),
        licence=db.licence,
        attribution_required=db.attribution_required,
        attribution=attribution(db, "" if db.no_record_notice else item_id),
        dropped=tuple(sorted(blocked)),
    )


class JapanSearch:
    """Search Japan Search, keeping only databases the :class:`Policy` allows.

    ``on_skip(database_id, reason)`` is called once per skipped database.
    Database terms are read once per instance (one request for all
    databases, plus one label request per ``restricted`` database used).
    """

    def __init__(
        self,
        fetch: Fetch = urllib_fetch,
        policy: Policy = Policy(),
        *,
        timeout: float = 15,
        on_skip: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.fetch = fetch
        self.policy = policy
        self.timeout = timeout
        self.on_skip = on_skip
        self._dbs: Optional[Dict[str, Database]] = None
        self._orgs: Optional[Dict[str, str]] = None
        self._blocked: Dict[str, FrozenSet[str]] = {}
        self._skipped: Dict[str, str] = {}

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        st, body = self.fetch(API + path, params or {}, self.timeout)
        if st != 200:
            raise RuntimeError(f"Japan Search {path}: HTTP {st}")
        return json.loads(body or "null")

    def databases(self) -> Dict[str, Database]:
        """All databases with their terms, by id (cached on the instance)."""
        if self._dbs is None:
            data = self._get("/database/search", {"size": 500}) or {}
            self._dbs = {}
            for d in data.get("list") or []:
                if isinstance(d, dict) and d.get("id"):
                    db = parse_database(d)
                    self._dbs[db.id] = db
        return self._dbs

    def organizations(self) -> Dict[str, str]:
        """Institution id → Japanese name, for credit lines (cached; ``{}`` on error)."""
        if self._orgs is None:
            try:
                data = self._get("/organization/search", {"size": 500}) or {}
            except Exception:  # only cosmetic: the credit line then has no institution
                data = {}
            self._orgs = {
                str(o.get("id")): str((o.get("name") or {}).get("ja") or "")
                for o in data.get("list") or []
                if isinstance(o, dict) and o.get("id")
            }
        return self._orgs

    def blocked_fields(self, db_id: str) -> FrozenSet[str]:
        """Common fields (``title``, ``contributor``, …) a database marks ``guionly``."""
        if db_id not in self._blocked:
            lab = self._get(f"/database/{db_id}/label") or {}
            gui = {
                str(f.get("originalPath"))
                for f in lab.get("fieldLabels") or []
                if isinstance(f, dict) and f.get("storeType") in ("guionly", "ignore")
            }
            self._blocked[db_id] = frozenset(
                str(c.get("commonType"))
                for c in lab.get("commonLabels") or []
                if isinstance(c, dict) and str(c.get("path")) in gui
            )
        return self._blocked[db_id]

    def check(self, db_id: str) -> str:
        """``""`` if ``db_id`` may be used under the policy, else the reason."""
        return self.policy.reason_to_skip(self.databases().get(db_id))

    def _skip(self, db_id: str, reason: str) -> None:
        if db_id not in self._skipped:
            self._skipped[db_id] = reason
            if self.on_skip:
                self.on_skip(db_id, reason)

    @property
    def skipped(self) -> Dict[str, str]:
        """Databases skipped so far and why."""
        return dict(self._skipped)

    def search(
        self,
        query: str = "",
        *,
        title: str = "",
        author: str = "",
        kind: str = "book",
        limit: int = 20,
        raw: bool = False,
    ) -> List[Record]:
        """Keyword search (``query`` or ``title``), optionally by ``author``
        (``q-contributor``). ``kind`` is a Japan Search ``f-type`` code
        (``book``, ``periodical``, …; ``""`` for all). At most ``limit``
        records after the policy is applied.
        """
        query, title, author = (query or "").strip(), (title or "").strip(), (author or "").strip()
        if not (query or title or author):
            raise ValueError("search needs a query, title or author")
        limit = max(1, min(int(limit), 100))
        params: Dict[str, Any] = {"size": limit}
        if query or title:
            params["keyword"] = query or title
        if author:
            params["q-contributor"] = author
        if kind:
            params["f-type"] = kind
        data = self._get("/item/search/jps-cross", params) or {}
        out: List[Record] = []
        for item in data.get("list") or []:
            rec = self._accept(item, raw)
            if rec is None:
                continue
            out.append(rec)
            if len(out) >= limit:
                break
        return out

    def _accept(self, item: Any, raw: bool) -> Optional[Record]:
        """Apply the policy to one API item; the :class:`Record` or ``None``."""
        if not isinstance(item, dict):
            return None
        common = item.get("common") or {}
        db_id = str(common.get("database") or "")
        db = self.databases().get(db_id)
        reason = self.policy.reason_to_skip(db)
        if not reason and db is not None and str(common.get("apiType") or db.api_type) == "ng":
            reason = "API use not allowed (apiType=ng)"
        if reason or db is None:
            self._skip(db_id, reason)
            return None
        blocked = self.blocked_fields(db_id) if db.api_type == "restricted" else frozenset()
        org = str(common.get("provider") or "")
        if not db.provider and org:
            name = self.organizations().get(org, "")
            if name:
                db = replace(db, provider=name)
        rec = _record(item, db, blocked)
        if rec is not None and raw:
            rec.raw = item
        return rec

    def item_ids_for_isbn(self, isbn: str) -> List[str]:
        """Item ids whose ``schema:identifier`` is exactly this ISBN.

        Uses the SPARQL endpoint (the keyword API is fuzzy for ISBNs) and
        asks for the spellings found in the data: ``ISBN:`` followed by the
        ISBN-13 or ISBN-10, plain or hyphenated. ``[]`` for an invalid ISBN.
        """
        literals = isbn_literals(isbn)
        if not literals:
            return []
        values = " ".join(json.dumps(v, ensure_ascii=False) for v in literals)
        query = (
            "PREFIX schema: <http://schema.org/> SELECT DISTINCT ?s WHERE { "
            f"VALUES ?id {{ {values} }} ?s schema:identifier ?id }} LIMIT 50"
        )
        st, body = self.fetch(SPARQL, {"query": query, "format": "json"}, self.timeout)
        if st != 200:
            raise RuntimeError(f"Japan Search SPARQL: HTTP {st}")
        rows = ((json.loads(body or "null") or {}).get("results") or {}).get("bindings") or []
        ids: List[str] = []
        for row in rows:
            uri = str(((row or {}).get("s") or {}).get("value") or "")
            if uri.startswith(SITE + "/data/"):
                item_id = uri[len(SITE + "/data/"):].split("#", 1)[0]
                if item_id and item_id not in ids:
                    ids.append(item_id)
        return ids

    def lookup(self, isbn: str, *, limit: int = 5, raw: bool = False) -> List[Record]:
        """Records whose identifier is exactly ``isbn``, after the policy.

        Databases the policy skips are left out before their items are
        fetched (the database id is the item id's prefix). Every record gets
        ``isbn`` (normalised to 13 digits) since the identifier matched.
        """
        isbn13 = to_isbn13(isbn, strict=True)
        if not isbn13:
            return []
        dbs = self.databases()
        out: List[Record] = []
        for item_id in self.item_ids_for_isbn(isbn13):
            db_id = item_id.split("-", 1)[0]
            reason = self.policy.reason_to_skip(dbs.get(db_id))
            if reason:
                self._skip(db_id, reason)
                continue
            try:
                item = self._get(f"/item/{item_id}")
            except RuntimeError:  # gone, or withheld from the API
                continue
            rec = self._accept(item, raw)
            if rec is None:
                continue
            rec.isbn = isbn13
            out.append(rec)
            if len(out) >= limit:
                break
        return out
