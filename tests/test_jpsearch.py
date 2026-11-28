"""Japan Search client: per-database terms, partial restrictions, attribution.

Synthetic fixtures shaped like the simple Web API responses; no network.
"""
import json

import pytest

from hondana.jpsearch import (
    DEFAULT_ACCEPT,
    Database,
    JapanSearch,
    Policy,
    attribution,
    classify_rights,
    parse_database,
)


def db(id, rights="", api="ok", name=None, provider=None, en=""):
    return {
        "id": id,
        "name": {"ja": name or f"{id}データベース", "en": en},
        "apiType": api,
        "metadataRights": {"ja": rights} if rights else {},
        "provider": provider,
    }


DATABASES = {
    "list": [
        db("natbib", '<p><a href="#">CC BY4.0</a>で利用できます。</p><p>個別のメタデータに表示を行う必要はありません。</p>',
           name="全国書誌", en="Japanese National Bibliography"),
        db("zero", "", name="ゼロ文庫", provider="ゼロ図書館"),
        db("nc", "CC BY-NC-SA 4.0"),
        db("own", "利用規約"),
        db("noway", "当館に無断で複製・転載・加工を行うことは禁止します。"),
        db("closed", "", api="ng"),
        db("part", "CC0", api="restricted", name="一部制限DB"),
        db("caveat", "CC BY 、データベース利用規定をご確認ください。"),
    ]
}

ORGS = {"list": [{"id": "natlib", "name": {"ja": "国立図書館"}}]}

LABEL_PART = {
    "id": "part",
    "fieldLabels": [
        {"path": "part-0-s", "originalPath": "0", "storeType": "normal"},
        {"path": "part-1-s", "originalPath": "1", "storeType": "normal"},
        {"path": "part-2-s", "originalPath": "2", "storeType": "guionly"},
    ],
    "commonLabels": [
        {"path": "0", "commonType": "id"},
        {"path": "1", "commonType": "title"},
        {"path": "2", "commonType": "contributor"},
    ],
}


def item(db_id, n, title, contributor=(), temporal=(), provider=None, api="ok", extra=None):
    common = {
        "id": f"{db_id}-{n}",
        "database": db_id,
        "apiType": api,
        "title": title,
        "contributor": list(contributor),
        "temporal": list(temporal),
        "linkUrl": f"https://example.org/{db_id}/{n}",
    }
    if provider:
        common["provider"] = provider
    it = {"id": f"{db_id}-{n}", "common": common}
    it.update(extra or {})
    return it


NDL_ITEM = item(
    "natbib", 1, "吾輩は猫である", ["夏目漱石 著", "岩波書店"], ["1990.4", "1990"], provider="natlib",
    extra={"natbib-rdf:RDF": {"dcndl:BibResource": {
        "dc:creator-s": "夏目漱石 著",
        "dcterms:publisher": {"foaf:Agent": {"foaf:name-s": "岩波書店"}},
        "dcterms:identifier_rdf:datatype_http://ndl_go_jp/dcndl/terms/ISBN-u": "http://iss.ndl.go.jp/isbn/4003101014",
    }}},
)

SEARCH = {
    "hit": 9,
    "list": [
        NDL_ITEM,
        item("zero", 1, "猫の本", ["猫山 著"], ["昭和10", "1935"]),
        item("nc", 1, "非営利の猫", ["誰か"]),
        item("own", 1, "独自規約の猫"),
        item("noway", 1, "禁止の猫"),
        item("closed", 1, "API不可の猫"),
        item("part", 1, "一部制限の猫", ["隠す人"], ["2001"], api="restricted"),
        item("caveat", 1, "注意書きの猫"),
        item("unknown", 1, "知らないDBの猫"),
    ],
}


def fake(calls=None, routes=None):
    routes = routes if routes is not None else {
        "/database/search": (200, json.dumps(DATABASES)),
        "/organization/search": (200, json.dumps(ORGS)),
        "/database/part/label": (200, json.dumps(LABEL_PART)),
        "/item/search/jps-cross": (200, json.dumps(SEARCH)),
    }

    def fetch(url, params, timeout):
        if calls is not None:
            calls.append((url, dict(params)))
        for k, v in routes.items():
            if url.endswith(k):
                return v
        return 404, ""

    return fetch


@pytest.mark.parametrize("text, expected", [
    ("", ("cc0", False)),
    ("CC0", ("cc0", False)),
    ("<p>CC BY4.0 で利用できます。</p>", ("cc-by", False)),
    ("CC-BY", ("cc-by", False)),
    ("ＣＣ　ＢＹ", ("cc-by", False)),
    ("Creative Commons 表示 4.0 国際", ("cc-by", False)),
    ("CC BY(政府標準利用規約(第2.0版)準拠)", ("cc-by", False)),
    ("CC BY-SA", ("cc-by-sa", False)),
    ("CC BY-NC-SA 4.0", ("cc-by-nc-sa", False)),
    ("CC BY-NC-ND", ("cc-by-nc-nd", False)),
    ("CC BY-ND", ("cc-by-nd", False)),
    ("政府標準利用規約（第2.0版）", ("gov", False)),
    ("公共データ利用規約（第1.0版）", ("pdl", False)),
    ("PDM", ("pdm", False)),
    ("二次利用不可", ("no-reuse", False)),
    ("メタデータの無断転用・無断転載をお断りいたします。", ("no-reuse", False)),
    ("利用規約", ("custom", False)),
    ("https://example.org/license", ("custom", False)),
    ("PDM、CC0、CC BY、CC BY-SAのいずれか", ("custom", False)),
    ("CC0(ただし解説はCC BY)", ("custom", False)),
    ("著作権あり-教育目的の利用可", ("custom", False)),
    ("CC0 ※ただし作品概要については著作権あり", ("cc0", True)),
    ("CC BY-SA 、データベース利用規定をご確認ください。", ("cc-by-sa", True)),
])
def test_classify_rights(text, expected):
    assert classify_rights(text) == expected


def test_nd_is_not_no_reuse():
    # 「改変禁止」 is the Japanese name of ND, not a ban on reuse
    assert classify_rights("CC BY-ND（表示—改変禁止）")[0] == "cc-by-nd"


def test_parse_database():
    d = parse_database(DATABASES["list"][0])
    assert (d.id, d.name, d.name_en, d.api_type, d.licence, d.caveat) == (
        "natbib", "全国書誌", "Japanese National Bibliography", "ok", "cc-by", False)
    assert d.no_record_notice and d.attribution_required
    assert d.rights.startswith("CC BY4.0") and "<" not in d.rights
    assert d.page_url == "https://jpsearch.go.jp/database/natbib"
    # an internal id is not used as the institution name
    assert parse_database(db("x", provider="libsomewhere")).provider == ""
    assert parse_database(db("x", provider="某市立図書館")).provider == "某市立図書館"


def test_policy_defaults():
    dbs = {d["id"]: parse_database(d) for d in DATABASES["list"]}
    p = Policy()
    assert p.accept == DEFAULT_ACCEPT
    ok = {k for k, d in dbs.items() if not p.reason_to_skip(d)}
    assert ok == {"natbib", "zero"}
    assert "apiType=ng" in p.reason_to_skip(dbs["closed"])
    assert "restricted" in p.reason_to_skip(dbs["part"])
    assert p.reason_to_skip(dbs["noway"]) == "terms forbid reuse"
    assert "Policy.allow" in p.reason_to_skip(dbs["caveat"])
    assert p.reason_to_skip(None).startswith("unknown database")


def test_policy_allow_and_accept_never_override_ng_or_no_reuse():
    dbs = {d["id"]: parse_database(d) for d in DATABASES["list"]}
    p = Policy(allow=frozenset({"own", "caveat", "closed", "noway"}), accept=DEFAULT_ACCEPT | {"cc-by-nc-sa"})
    assert p.reason_to_skip(dbs["own"]) == ""
    assert p.reason_to_skip(dbs["caveat"]) == ""
    assert p.reason_to_skip(dbs["nc"]) == ""
    assert p.reason_to_skip(dbs["closed"]) != ""
    assert p.reason_to_skip(dbs["noway"]) != ""
    assert Policy(deny=frozenset({"zero"})).reason_to_skip(dbs["zero"]) == "denied by Policy.deny"


def test_attribution_formats():
    d = Database("zero", "ゼロ文庫", "Zero Library", "ゼロ図書館")
    assert attribution(d) == "出典：ジャパンサーチ「ゼロ文庫（ゼロ図書館）」のメタデータ（https://jpsearch.go.jp/database/zero）"
    assert attribution(d, "zero-1", modified=True) == (
        "出典：ジャパンサーチ「ゼロ文庫（ゼロ図書館）」のメタデータを改変して利用（https://jpsearch.go.jp/item/zero-1）")
    assert attribution(Database("x"), lang="en") == 'Source: Japan Search, "x" metadata (https://jpsearch.go.jp/database/x)'


def test_search_applies_policy_and_reports_skips():
    calls, skipped = [], []
    js = JapanSearch(fake(calls), on_skip=lambda d, r: skipped.append(d))
    recs = js.search(title="猫", author="夏目漱石", limit=5)
    assert [r.database for r in recs] == ["natbib", "zero"]
    assert set(skipped) == {"nc", "own", "noway", "closed", "part", "caveat", "unknown"}
    assert set(js.skipped) == set(skipped)
    [(url, params)] = [c for c in calls if "/item/" in c[0]]
    assert url == "https://jpsearch.go.jp/api/item/search/jps-cross"
    assert params == {"size": 5, "keyword": "猫", "q-contributor": "夏目漱石", "f-type": "book"}
    # no label request for a database that was skipped anyway
    assert not any(u.endswith("/label") for u, _ in calls)


def test_ndl_record_fields_and_attribution():
    js = JapanSearch(fake())
    r = js.search("猫")[0]
    assert (r.title, r.author, r.publisher, r.year, r.isbn) == (
        "吾輩は猫である", "夏目漱石 著", "岩波書店", "1990", "9784003101018")
    assert r.licence == "cc-by" and r.attribution_required
    # "個別のメタデータに表示を行う必要はありません" → credit the database, not each item
    assert r.attribution == "出典：ジャパンサーチ「全国書誌（国立図書館）」のメタデータ（https://jpsearch.go.jp/database/natbib）"
    assert r.url == "https://jpsearch.go.jp/item/natbib-1"
    assert r.link == "https://example.org/natbib/1"
    b = r.to_book()
    assert (b.isbn, b.title, b.source) == ("9784003101018", "吾輩は猫である", "Japan Search")


def test_ndl_record_with_printed_isbn_field():
    # dignl-style items carry "…ISBN-s": "4-634-34250-2" instead of the -u URI
    it = item("natbib", 2, "海の道と東西の出会い", ["青木康征 著"], ["1998"], extra={"natbib-rdf:RDF": {
        "dcndl:BibResource": {"dcterms:identifier_rdf:datatype_http://ndl_go_jp/dcndl/terms/ISBN-s": "4-634-34250-2"}}})
    routes = {
        "/database/search": (200, json.dumps(DATABASES)),
        "/organization/search": (200, json.dumps(ORGS)),
        "/item/search/jps-cross": (200, json.dumps({"list": [it]})),
    }
    assert JapanSearch(fake(routes=routes)).search("海")[0].isbn == "9784634342507"


def test_generic_record_uses_common_fields_and_item_link():
    r = JapanSearch(fake()).search("猫")[1]
    assert (r.title, r.author, r.publisher, r.year, r.isbn) == ("猫の本", "猫山 著", "", "1935", "")
    assert r.licence == "cc0" and not r.attribution_required
    assert r.attribution == "出典：ジャパンサーチ「ゼロ文庫（ゼロ図書館）」のメタデータ（https://jpsearch.go.jp/item/zero-1）"


def test_restricted_drops_guionly_fields():
    calls = []
    js = JapanSearch(fake(calls), Policy(restricted=True))
    recs = {r.database: r for r in js.search("猫")}
    r = recs["part"]
    assert r.title == "一部制限の猫"
    assert r.author == "" and r.dropped == ("contributor",)
    assert js.blocked_fields("part") == frozenset({"contributor"})
    assert sum(u.endswith("/database/part/label") for u, _ in calls) == 1


def test_restricted_record_without_usable_title_is_dropped():
    label = dict(LABEL_PART, fieldLabels=[dict(f, storeType="guionly") for f in LABEL_PART["fieldLabels"]])
    routes = {
        "/database/search": (200, json.dumps(DATABASES)),
        "/database/part/label": (200, json.dumps(label)),
        "/item/search/jps-cross": (200, json.dumps({"list": [SEARCH["list"][6]]})),
    }
    assert JapanSearch(fake(routes=routes), Policy(restricted=True)).search("猫") == []


def test_item_flagged_ng_is_skipped_even_if_database_list_says_ok():
    routes = {
        "/database/search": (200, json.dumps(DATABASES)),
        "/item/search/jps-cross": (200, json.dumps({"list": [item("zero", 2, "急に不可", api="ng")]})),
    }
    skipped = []
    assert JapanSearch(fake(routes=routes), on_skip=lambda d, r: skipped.append((d, r))).search("猫") == []
    assert skipped == [("zero", "API use not allowed (apiType=ng)")]


def test_databases_cached_and_errors():
    calls = []
    js = JapanSearch(fake(calls))
    js.search("猫")
    js.search("犬")
    assert sum(u.endswith("/database/search") for u, _ in calls) == 1
    assert sum(u.endswith("/organization/search") for u, _ in calls) == 1
    with pytest.raises(RuntimeError):
        JapanSearch(fake(routes={})).search("猫")
    with pytest.raises(ValueError):
        js.search()


def test_organization_lookup_failure_only_affects_credit_line():
    routes = {
        "/database/search": (200, json.dumps(DATABASES)),
        "/item/search/jps-cross": (200, json.dumps({"list": [NDL_ITEM]})),
    }
    r = JapanSearch(fake(routes=routes)).search("猫")[0]
    assert r.attribution.startswith("出典：ジャパンサーチ「全国書誌」のメタデータ")


def test_kind_and_limit_and_raw():
    calls = []
    js = JapanSearch(fake(calls))
    recs = js.search("猫", kind="", limit=1, raw=True)
    assert len(recs) == 1 and recs[0].raw["id"] == "natbib-1"
    searches = [p for u, p in calls if "/item/" in u]
    assert "f-type" not in searches[0] and searches[0]["size"] == 1
    js.search("猫", limit=1000)
    assert [p for u, p in calls if "/item/" in u][-1]["size"] == 100


# --- search(sources=(..., "jpsearch")) ---------------------------------------

from hondana import Book, search  # noqa: E402


def test_search_source_keeps_licence_and_attribution():
    skipped = []
    books = search("猫", sources=("jpsearch",), fetch=fake(), limit=10,
                   on_skip=lambda d, r: skipped.append(d))
    by_title = {b.title: b for b in books}
    assert set(by_title) == {"吾輩は猫である", "猫の本"}
    cat = by_title["吾輩は猫である"]
    assert cat.source == "Japan Search"
    assert cat.isbn == "9784003101018"
    assert cat.licence == "cc-by"
    assert cat.attribution.startswith("出典：ジャパンサーチ「全国書誌（国立図書館）」")
    zero = by_title["猫の本"]
    assert zero.licence == "cc0" and "/item/zero-1" in zero.attribution
    assert set(skipped) == {"nc", "own", "noway", "closed", "part", "caveat", "unknown"}
    d = cat.to_dict()
    assert d["licence"] == "cc-by" and d["attribution"] == cat.attribution


def test_search_source_policy_is_passed_through():
    books = search("猫", sources=("jpsearch",), fetch=fake(), limit=10,
                   jpsearch_policy=Policy(restricted=True, allow=frozenset({"own"})))
    titles = {b.title for b in books}
    assert {"一部制限の猫", "独自規約の猫"} <= titles
    part = next(b for b in books if b.title == "一部制限の猫")
    assert part.author == ""  # contributor is guionly in that database


def test_search_source_is_opt_in_and_other_books_unchanged():
    calls = []
    search("猫", fetch=fake(calls), limit=3)
    assert not any("jpsearch.go.jp" in u for u, _ in calls)
    d = Book("9784003101018", "吾輩は猫である").to_dict()
    assert "licence" not in d and "attribution" not in d


def test_search_source_earlier_source_wins_same_isbn():
    ndl = (200, """<?xml version="1.0"?><rss><channel><item><title>吾輩は猫である</title>
<dc:creator>夏目漱石</dc:creator><dc:identifier xsi:type="dcndl:ISBN">978-4-00-310101-8</dc:identifier>
</item></channel></rss>""")
    routes = {
        "/database/search": (200, json.dumps(DATABASES)),
        "/organization/search": (200, json.dumps(ORGS)),
        "/item/search/jps-cross": (200, json.dumps(SEARCH)),
    }
    jp = fake(routes=routes)

    def fetch(url, params, timeout):
        return ndl if "ndlsearch" in url else jp(url, params, timeout)

    books = search("吾輩は猫である", sources=("ndl", "jpsearch"), fetch=fetch, limit=10)
    same = [b for b in books if b.isbn == "9784003101018"]
    assert len(same) == 1 and same[0].source == "NDL" and same[0].attribution == ""


def test_search_source_errors_and_raw_and_timeouts():
    errors = []
    books = search("猫", sources=("jpsearch",), fetch=fake(routes={}), on_error=lambda n, e: errors.append(n))
    assert books == [] and errors == ["jpsearch"]
    seen = []

    def slow(url, params, timeout):
        seen.append(timeout)
        return fake()(url, params, timeout)

    books = search("猫", sources=("jpsearch",), fetch=slow, raw=True, timeouts={"jpsearch": 3})
    assert seen and set(seen) == {3}
    assert all(b.raw and json.loads(b.raw)["common"]["title"] == b.title for b in books)
    with pytest.raises(ValueError):
        search("猫", sources=("jpsearch", "nope"), fetch=fake())


# --- CLI: hondana search --source jpsearch -----------------------------------

def test_cli_search_jpsearch_table_prints_credit_lines(monkeypatch, capsys):
    import hondana.__main__ as cli
    real = cli.search

    def patched(*a, **kw):
        kw["fetch"] = fake()
        return real(*a, **kw)

    monkeypatch.setattr(cli, "search", patched)
    assert cli.main(["search", "猫", "--source", "jpsearch", "--format", "table"]) == 0
    out, err = capsys.readouterr()
    assert "吾輩は猫である" in out and "Japan Search" in out
    assert "出典 / Sources:" in out
    assert "- 猫の本 [cc0]: 出典：ジャパンサーチ「ゼロ文庫（ゼロ図書館）」のメタデータ（https://jpsearch.go.jp/item/zero-1）" in out
    assert "# jpsearch: skipped database closed (API use not allowed (apiType=ng))" in err
    assert "非営利の猫" not in out


def test_cli_search_jpsearch_policy_flags_and_exports(monkeypatch, capsys):
    import hondana.__main__ as cli
    real = cli.search
    seen = {}

    def patched(*a, **kw):
        seen.update(kw)
        kw["fetch"] = fake()
        return real(*a, **kw)

    monkeypatch.setattr(cli, "search", patched)
    rc = cli.main(["search", "猫", "--source", "jpsearch", "--source", "jpsearch", "--jp-restricted",
                   "--jp-allow", "own", "--jp-accept", "cc-by-nc-sa", "--jp-deny", "zero", "--format", "ris"])
    assert rc == 0
    pol = seen["jpsearch_policy"]
    assert seen["sources"] == ("jpsearch",)
    assert pol.restricted and pol.allow == {"own"} and pol.deny == {"zero"} and "cc-by-nc-sa" in pol.accept
    out, err = capsys.readouterr()
    assert "TI  - 非営利の猫" in out and "猫の本" not in out
    assert "# 非営利の猫: 出典：ジャパンサーチ" in err  # credit line kept on stderr
    rc = cli.main(["search", "猫", "--source", "jpsearch", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0 and all(d["source"] == "Japan Search" and d["attribution"] for d in data)


def test_cli_search_default_sources_have_no_policy(monkeypatch, capsys):
    import hondana.__main__ as cli
    seen = {}

    def patched(*a, **kw):
        seen.update(kw)
        return []

    monkeypatch.setattr(cli, "search", patched)
    assert cli.main(["search", "猫"]) == 1
    assert seen["sources"] == ("ndl", "openlibrary") and seen["jpsearch_policy"] is None


def test_cli_search_same_credit_line_printed_once(monkeypatch, capsys):
    import hondana.__main__ as cli
    from hondana import Book

    books = [Book("", t, source="Japan Search", licence="cc-by", attribution="出典：X（https://jpsearch.go.jp/database/x）")
             for t in ("上巻", "下巻", "上巻")]
    monkeypatch.setattr(cli, "search", lambda *a, **kw: books)
    assert cli.main(["search", "猫", "--source", "jpsearch", "--format", "table"]) == 0
    out = capsys.readouterr().out
    assert out.count("出典：X") == 1 and "- 上巻 / 下巻 [cc-by]: 出典：X" in out


# --- exact ISBN route (SPARQL) and lookup(order=(..., "jpsearch")) -----------

from hondana import lookup  # noqa: E402
from hondana.jpsearch import isbn_literals  # noqa: E402


def sparql(*uris):
    return (200, json.dumps({"head": {"vars": ["s"]}, "results": {"bindings": [
        {"s": {"type": "uri", "value": u}} for u in uris]}}))


DIGNL_LIKE = item("natbib", 9, "海の道と東西の出会い", ["青木康征 著"], ["1998.2", "1998"], provider="natlib")
OWN_ITEM = item("own", 3, "独自規約の海")


def isbn_routes(**extra):
    r = {
        "/database/search": (200, json.dumps(DATABASES)),
        "/organization/search": (200, json.dumps(ORGS)),
        "/rdf/sparql/": sparql(
            "https://jpsearch.go.jp/data/closed-5",
            "https://jpsearch.go.jp/data/own-3",
            "https://jpsearch.go.jp/data/natbib-9",
            "https://jpsearch.go.jp/data/natbib-9#accessinfo",
            "https://example.org/other",
        ),
        "/item/natbib-9": (200, json.dumps(DIGNL_LIKE)),
        "/item/own-3": (200, json.dumps(OWN_ITEM)),
    }
    r.update(extra)
    return r


def test_isbn_literals_cover_the_spellings_in_the_data():
    assert isbn_literals("978-4-00-310101-8") == [
        "ISBN:9784003101018", "ISBN:978-4-00-310101-8", "ISBN:4003101014", "ISBN:4-00-310101-4"]
    assert isbn_literals("9791032300824") == ["ISBN:9791032300824", "ISBN:979-10-323-0082-4"]
    assert isbn_literals("4003101015") == []


def test_item_ids_for_isbn_queries_exact_identifiers():
    calls = []
    js = JapanSearch(fake(calls, isbn_routes()))
    assert js.item_ids_for_isbn("4634342502") == ["closed-5", "own-3", "natbib-9"]
    url, params = calls[0]
    assert url == "https://jpsearch.go.jp/rdf/sparql/" and params["format"] == "json"
    assert '"ISBN:4-634-34250-2"' in params["query"] and "schema:identifier" in params["query"]
    assert js.item_ids_for_isbn("bad") == [] and len(calls) == 1


def test_lookup_skips_by_policy_before_fetching_items():
    calls, skipped = [], {}
    js = JapanSearch(fake(calls, isbn_routes()), on_skip=skipped.__setitem__)
    recs = js.lookup("4-634-34250-2")
    assert [r.id for r in recs] == ["natbib-9"]
    r = recs[0]
    assert r.isbn == "9784634342507" and r.licence == "cc-by" and r.attribution.endswith("/database/natbib）")
    fetched = [u for u, _ in calls if "/item/" in u]
    assert fetched == ["https://jpsearch.go.jp/api/item/natbib-9"]  # closed / own never fetched
    assert set(skipped) == {"closed", "own"}
    assert JapanSearch(fake(routes=isbn_routes()), Policy(allow=frozenset({"own"}))).lookup(
        "4634342502", limit=1)[0].id == "own-3"


def test_lookup_item_gone_or_no_hits():
    routes = isbn_routes(**{"/item/natbib-9": (404, "")})
    assert JapanSearch(fake(routes=routes)).lookup("4634342502") == []
    routes = isbn_routes(**{"/rdf/sparql/": sparql()})
    assert JapanSearch(fake(routes=routes)).lookup("4634342502") == []
    with pytest.raises(RuntimeError):
        JapanSearch(fake(routes=isbn_routes(**{"/rdf/sparql/": (503, "")}))).lookup("4634342502")


def test_hondana_lookup_with_jpsearch_source():
    b = lookup("4634342502", order=("jpsearch",), fetch=fake(routes=isbn_routes()))
    assert (b.isbn, b.title, b.source, b.licence) == ("9784634342507", "海の道と東西の出会い", "Japan Search", "cc-by")
    assert b.attribution.startswith("出典：ジャパンサーチ「全国書誌（国立図書館）」")
    b = lookup("4634342502", order=("jpsearch",), fetch=fake(routes=isbn_routes()), raw=True)
    assert json.loads(b.raw)["id"] == "natbib-9"
    skipped = []
    assert lookup("4634342502", order=("jpsearch",), fetch=fake(routes=isbn_routes()),
                  jpsearch_policy=Policy(deny=frozenset({"natbib"})), on_skip=lambda d, r: skipped.append(d)) is None
    assert "natbib" in skipped


def test_hondana_lookup_merge_keeps_credit_only_when_used():
    openbd = (200, json.dumps([{"summary": {"title": "海の道と東西の出会い", "author": "青木康征", "publisher": "", "pubdate": ""}}]))
    jp = fake(routes=isbn_routes())

    def fetch(url, params, timeout):
        return openbd if "openbd" in url else jp(url, params, timeout)

    b = lookup("4634342502", order=("openbd", "jpsearch"), fetch=fetch, merge=True)
    assert b.source == "openBD+Japan Search" and b.year == "1998" and b.attribution  # year came from Japan Search
    full = (200, json.dumps([{"summary": {"title": "海", "author": "a", "publisher": "p", "pubdate": "1998", "cover": "https://c"}}]))
    b = lookup("4634342502", order=("openbd", "jpsearch"), merge=True,
               fetch=lambda u, p, t: full if "openbd" in u else jp(u, p, t))
    assert b.source == "openBD" and b.attribution == "" and b.licence == ""


def test_cli_lookup_source_jpsearch(monkeypatch, capsys):
    import hondana.__main__ as cli
    real = cli.lookup_many
    seen = {}

    def patched(*a, **kw):
        seen.update(kw)
        kw["fetch"] = fake(routes=isbn_routes())
        kw["rate"] = 0
        return real(*a, **kw)

    monkeypatch.setattr(cli, "lookup_many", patched)
    assert cli.main(["lookup", "4634342502", "--source", "jpsearch", "--format", "table"]) == 0
    out, err = capsys.readouterr()
    assert seen["order"] == ("jpsearch",) and seen["jpsearch_policy"] is not None
    assert "海の道と東西の出会い" in out and "出典 / Sources:" in out
    assert "# jpsearch: skipped database closed" in err
    assert cli.main(["lookup", "4634342502", "--source", "jpsearch", "--jp-allow", "own", "--format", "bibtex"]) == 0
    out, err = capsys.readouterr()
    assert "# 独自規約の海: 出典：ジャパンサーチ「ownデータベース」" in err  # first allowed hit
    assert seen["jpsearch_policy"].allow == {"own"}


def test_cli_lookup_default_order_unchanged(monkeypatch, capsys):
    import hondana.__main__ as cli
    from hondana.lookup import DEFAULT_ORDER
    seen = {}
    monkeypatch.setattr(cli, "lookup_many", lambda *a, **kw: seen.update(kw) or [None])
    assert cli.main(["lookup", "9784003101018"]) == 1
    assert seen["order"] == DEFAULT_ORDER and seen["jpsearch_policy"] is None
