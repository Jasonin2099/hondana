import json
from hondana import lookup

ISBN = "9784003101018"


def fake(responses, calls=None):
    def fetch(url, params, timeout):
        if calls is not None:
            calls.append(url)
        for k, v in responses.items():
            if k in url:
                if isinstance(v, Exception):
                    raise v
                return v
        return 404, ""
    return fetch


OBD = (200, json.dumps([{"summary": {"title": "吾輩は猫である", "author": "夏目漱石", "publisher": "岩波書店", "pubdate": "19900401", "cover": ""}}]))
NDL = (200, "<rss><item><title>吾輩は猫である</title><dc:creator>夏目, 漱石</dc:creator><dc:publisher>岩波書店</dc:publisher><dcterms:issued>1990</dcterms:issued></item></rss>")
GB = (200, json.dumps({"items": [{"volumeInfo": {"title": "吾輩は猫である", "authors": ["夏目漱石"], "imageLinks": {"thumbnail": "http://x/c.jpg&edge=curl"}}}]}))
OL = (200, json.dumps({"ISBN:" + ISBN: {"title": "I Am a Cat", "authors": [{"name": "Natsume Soseki"}], "publish_date": "March 1990"}}))


def test_first_source_wins():
    calls = []
    b = lookup("4003101014", fetch=fake({"openbd": OBD, "ndl": NDL}, calls))
    assert b.source == "openBD" and b.year == "1990" and len(calls) == 1


def test_fallback_on_error_and_empty():
    errs = []
    b = lookup(ISBN, fetch=fake({"openbd": (200, "[null]"), "ndl": TimeoutError(), "google": GB}), on_error=lambda n, e: errs.append(n))
    assert b.source == "Google Books" and b.cover == "https://x/c.jpg"
    assert errs == ["ndl"]


def test_open_library_last():
    b = lookup(ISBN, fetch=fake({"openlibrary": OL}))
    assert b.source == "Open Library" and b.year == "1990"


def test_invalid_and_missing():
    assert lookup("123", fetch=fake({})) is None
    assert lookup(ISBN, fetch=fake({})) is None




def test_cached_fetch_reuses_answers_until_ttl():
    from hondana import cached
    calls, now = [], [0.0]
    f = cached(fake({"openbd": OBD}, calls), ttl=60, clock=lambda: now[0])
    assert lookup(ISBN, fetch=f).source == "openBD"
    assert lookup(ISBN, fetch=f).source == "openBD"
    assert len(calls) == 1
    now[0] = 61
    lookup(ISBN, fetch=f)
    assert len(calls) == 2


def test_cached_fetch_keeps_404_but_not_errors():
    from hondana import cached
    calls = []
    f = cached(fake({"ndl": (503, "")}, calls))
    lookup(ISBN, fetch=f)
    lookup(ISBN, fetch=f)
    # openbd/google/openlibrary 404 → cached; ndl 503 → asked twice
    assert sorted(set(calls)) == sorted(calls[:4]) and len(calls) == 5
    assert sum("ndl" in c for c in calls) == 2


def test_cached_fetch_evicts_when_full():
    from hondana import cached
    calls, now = [], [0.0]
    f = cached(fake({"a": (200, "x")}, calls), ttl=100, maxsize=2, clock=lambda: now[0])
    for i in range(3):
        now[0] = i
        f("https://a/%d" % i, {}, 1)
    f("https://a/2", {}, 1)  # still cached
    f("https://a/0", {}, 1)  # oldest was dropped
    assert calls == ["https://a/0", "https://a/1", "https://a/2", "https://a/0"]


def test_per_source_timeouts():
    import pytest
    seen = {}

    def fetch(url, params, timeout):
        seen[url.split("/")[2]] = timeout
        return 404, ""

    lookup(ISBN, fetch=fetch, timeouts={"ndl": 30, "google": 2})
    assert seen == {"api.openbd.jp": 8, "ndlsearch.ndl.go.jp": 30, "www.googleapis.com": 2, "openlibrary.org": 8}
    with pytest.raises(ValueError, match="ndI"):
        lookup(ISBN, fetch=fetch, timeouts={"ndI": 30})


def test_raw_payload_behind_flag():
    b = lookup(ISBN, fetch=fake({"openbd": (200, "[null]"), "ndl": NDL}))
    assert b.raw is None and "raw" not in b.to_dict()
    b = lookup(ISBN, fetch=fake({"openbd": (200, "[null]"), "ndl": NDL}), raw=True)
    assert b.source == "NDL" and b.raw == NDL[1]
    assert b.to_dict()["raw"] == NDL[1]
    assert "raw" not in repr(b)
    assert b == lookup(ISBN, fetch=fake({"ndl": NDL}))


CINII = (200, json.dumps({"@graph": [{"items": [{"title": "吾輩は猫である", "dc:creator": "夏目漱石 [著]", "dc:publisher": ["岩波書店"], "dc:date": "1990"}]}]}))


def test_cinii_is_optional():
    calls = []
    assert lookup(ISBN, fetch=fake({"ci.nii": CINII}, calls)) is None
    assert not any("ci.nii" in c for c in calls)


def test_cinii_source(monkeypatch):
    seen = []

    def fetch(url, params, timeout):
        seen.append(params)
        return fake({"ci.nii": CINII})(url, params, timeout)

    monkeypatch.setenv("HONDANA_CINII_APPID", "demo")
    b = lookup(ISBN, fetch=fetch, order=("openbd", "cinii"))
    assert b.source == "CiNii Books" and b.publisher == "岩波書店" and b.year == "1990"
    assert seen[-1]["appid"] == "demo"


def test_cinii_empty_graph():
    assert lookup(ISBN, fetch=fake({"ci.nii": (200, json.dumps({"@graph": [{"items": []}]}))}), order=("cinii",)) is None


# --- merge across sources ----------------------------------------------------

# openBD with title+author only; NDL fills publisher+year; Google fills cover.
OBD_SPARSE = (200, json.dumps([{"summary": {"title": "吾輩は猫である", "author": "夏目漱石", "publisher": "", "pubdate": "", "cover": ""}}]))
NDL_SPARSE = (200, "<rss><item><title>吾輩は猫である</title><dc:creator></dc:creator><dc:publisher>岩波書店</dc:publisher><dcterms:issued>1990</dcterms:issued></item></rss>")
GB_COVER = (200, json.dumps({"items": [{"volumeInfo": {"title": "I Am a Cat", "authors": ["Other"], "publisher": "Other Pub", "publishedDate": "2000", "imageLinks": {"thumbnail": "http://x/c.jpg"}}}]}))


def test_merge_fills_missing_fields():
    b = lookup(
        ISBN,
        fetch=fake({"openbd": OBD_SPARSE, "ndl": NDL_SPARSE, "google": GB_COVER, "openlibrary": OL}),
        merge=True,
    )
    assert b.title == "吾輩は猫である"
    assert b.author == "夏目漱石"          # from openBD (first)
    assert b.publisher == "岩波書店"       # from NDL
    assert b.year == "1990"                # from NDL
    assert b.cover == "https://x/c.jpg"    # from Google
    assert b.source == "openBD+NDL+Google Books"


def test_merge_first_nonempty_wins_per_field():
    # openBD already has publisher; NDL's must not overwrite.
    b = lookup(ISBN, fetch=fake({"openbd": OBD, "ndl": NDL_SPARSE}), merge=True)
    assert b.publisher == "岩波書店" and b.year == "1990"
    assert b.source == "openBD"  # NDL added nothing new (title/author/publisher/year already set by OBD; NDL year same filled from OBD already)


def test_merge_false_still_first_wins():
    calls = []
    b = lookup(ISBN, fetch=fake({"openbd": OBD_SPARSE, "ndl": NDL}, calls), merge=False)
    assert b.source == "openBD" and b.publisher == "" and len(calls) == 1


def test_merge_raw_keeps_first_body():
    b = lookup(
        ISBN,
        fetch=fake({"openbd": OBD_SPARSE, "ndl": NDL_SPARSE}),
        merge=True,
        raw=True,
    )
    assert b.raw == OBD_SPARSE[1]
    assert "openBD" in b.source and "NDL" in b.source


def test_merge_none_when_all_miss():
    assert lookup(ISBN, fetch=fake({}), merge=True) is None


# --- lookup_many -------------------------------------------------------------

def test_lookup_many_preserves_order_and_nones():
    from hondana import lookup_many
    other = "9784873117782"
    ol_other = (200, json.dumps({"ISBN:" + other: {"title": "Other Book", "authors": [{"name": "A"}], "publish_date": "2015"}}))
    books = lookup_many(
        ["123", ISBN, other],
        fetch=fake({"openbd": OBD, "openlibrary.org/api/books": ol_other}),
        order=("openbd", "openlibrary"),
    )
    assert books[0] is None
    assert books[1].title == "吾輩は猫である" and books[1].source == "openBD"
    # second ISBN: openbd returns same OBD payload keyed only by URL host match —
    # fake matches substring in URL, so openbd hits for both; that's fine.
    assert books[2] is not None and books[2].title  # found via openbd fake


def test_lookup_many_rate_sleeps_between_items():
    from hondana import lookup_many
    slept = []
    lookup_many(
        [ISBN, ISBN, "123"],
        fetch=fake({"openbd": OBD}),
        rate=0.5,
        sleep=slept.append,
    )
    assert slept == [0.5, 0.5]


def test_lookup_many_rate_zero_no_sleep():
    from hondana import lookup_many
    slept = []
    lookup_many([ISBN, ISBN], fetch=fake({"openbd": OBD}), rate=0, sleep=slept.append)
    assert slept == []
