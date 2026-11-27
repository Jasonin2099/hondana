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
