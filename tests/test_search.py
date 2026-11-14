"""Title/author search (NDL + Open Library) and openBD classifiers."""
import json
import pytest
from hondana import Book, lookup, search
from hondana.__main__ import main
from hondana.lookup import _openbd_classifiers


ISBN = "9784003101018"

NDL_SEARCH = (200, """<?xml version="1.0"?><rss><channel>
<item>
  <title>吾輩は猫である</title>
  <dc:creator>夏目, 漱石</dc:creator>
  <dc:publisher>岩波書店</dc:publisher>
  <dcterms:issued>1990</dcterms:issued>
  <dc:identifier xsi:type="dcndl:ISBN">978-4-00-310101-8</dc:identifier>
</item>
<item>
  <title>続・吾輩は猫である 案内</title>
  <dc:creator>別人</dc:creator>
  <dc:publisher>某社</dc:publisher>
  <dcterms:issued>2001</dcterms:issued>
</item>
</channel></rss>""")

OL_SEARCH = (200, json.dumps({
    "docs": [
        {
            "title": "I Am a Cat",
            "author_name": ["Natsume Soseki"],
            "publisher": ["Tuttle"],
            "first_publish_year": 1970,
            "isbn": ["9780804832410"],
            "cover_i": 123,
        },
        {
            "title": "吾輩は猫である",
            "subtitle": "改版",
            "author_name": ["夏目漱石"],
            "first_publish_year": 1990,
            "isbn": ["9784003101018"],
        },
    ]
}))


def fake(responses, calls=None):
    def fetch(url, params, timeout):
        if calls is not None:
            calls.append((url, dict(params), timeout))
        for k, v in responses.items():
            if k in url:
                if isinstance(v, Exception):
                    raise v
                return v
        return 404, ""
    return fetch


def test_search_ranks_folded_title_first():
    books = search("吾輩は猫である", fetch=fake({
        "ndlsearch": NDL_SEARCH,
        "openlibrary.org/search": OL_SEARCH,
    }))
    assert books[0].title == "吾輩は猫である" and books[0].source == "NDL"
    assert books[0].isbn == "9784003101018"
    # The Open Library record with the same ISBN is merged away; the English
    # title (a different ISBN) remains, ranked below the exact Japanese match.
    titles = [b.title for b in books]
    assert "I Am a Cat" in titles
    assert any(b.source == "Open Library" for b in books)
    assert all("改版" not in t for t in titles)


def test_search_title_author_params_and_limit():
    calls = []
    books = search(
        title="吾輩は猫である",
        author="夏目漱石",
        limit=1,
        fetch=fake({"ndlsearch": NDL_SEARCH, "openlibrary.org/search": OL_SEARCH}, calls),
    )
    assert len(books) == 1
    ndl = [c for c in calls if "ndlsearch" in c[0]][0]
    assert ndl[1]["title"] == "吾輩は猫である" and ndl[1]["creator"] == "夏目漱石"
    assert "any" not in ndl[1]


def test_search_query_uses_any_and_q():
    calls = []
    search("猫", fetch=fake({"ndlsearch": NDL_SEARCH, "openlibrary.org/search": OL_SEARCH}, calls))
    ndl = [c for c in calls if "ndlsearch" in c[0]][0]
    ol = [c for c in calls if "openlibrary.org/search" in c[0]][0]
    assert ndl[1]["any"] == "猫"
    assert ol[1]["q"] == "猫"


def test_search_dedupes_by_isbn_across_sources():
    # Same ISBN from both sources: keep the first (NDL, given default order).
    books = search(
        "吾輩は猫である",
        fetch=fake({"ndlsearch": NDL_SEARCH, "openlibrary.org/search": OL_SEARCH}),
        sources=("ndl", "openlibrary"),
    )
    isbns = [b.isbn for b in books if b.isbn == ISBN]
    assert isbns == [ISBN]


def test_search_skips_failing_source():
    errs = []
    books = search(
        "吾輩は猫である",
        fetch=fake({"ndlsearch": TimeoutError(), "openlibrary.org/search": OL_SEARCH}),
        on_error=lambda n, e: errs.append(n),
    )
    assert errs == ["ndl"]
    assert books and books[0].source == "Open Library"


def test_search_requires_a_query():
    with pytest.raises(ValueError, match="query"):
        search(fetch=fake({}))


def test_search_unknown_source():
    with pytest.raises(ValueError, match="unknown"):
        search("猫", sources=("google",), fetch=fake({}))


def test_cli_search_table(monkeypatch, capsys):
    import hondana.__main__ as cli

    def fake_search(*args, **kw):
        return [Book(ISBN, "吾輩は猫である", "夏目漱石", "岩波書店", "1990", source="NDL")]

    monkeypatch.setattr(cli, "search", fake_search)
    assert cli.main(["search", "吾輩は猫である", "--format", "table"]) == 0
    out = capsys.readouterr().out
    assert "吾輩は猫である" in out and "NDL" in out


def test_cli_search_no_query(monkeypatch, capsys):
    import io
    import hondana.__main__ as cli
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert cli.main(["search"]) == 1
    assert "no query" in capsys.readouterr().err


# --- openBD C-code / NDC -----------------------------------------------------

OBD_CLASSIFIED = (200, json.dumps([{
    "summary": {
        "title": "退屈なことはPythonにやらせよう",
        "author": "Al Sweigart／著",
        "publisher": "オライリー・ジャパン",
        "pubdate": "20170325",
        "cover": "",
    },
    "onix": {
        "DescriptiveDetail": {
            "Subject": [
                {"SubjectSchemeIdentifier": "78", "SubjectCode": "C3055"},
                {"SubjectSchemeIdentifier": "79", "SubjectCode": "12"},
            ]
        }
    },
    "hanmoto": {"ndccode": "007.64", "ccode": "3055"},
}]))


def test_openbd_parses_ccode_and_ndc():
    ccode, ndc = _openbd_classifiers(json.loads(OBD_CLASSIFIED[1])[0])
    assert ccode == "3055"  # leading C dropped
    assert ndc == "007.64"
    # scheme 79 is the genre code, not NDC
    payload = {"onix": {"DescriptiveDetail": {"Subject": [
        {"SubjectSchemeIdentifier": "79", "SubjectCode": "12"}
    ]}}, "hanmoto": {}}
    assert _openbd_classifiers(payload) == ("", "")


def test_lookup_fills_ccode_and_ndc():
    b = lookup(ISBN, fetch=fake({"openbd": OBD_CLASSIFIED}))
    assert b is not None
    assert b.ccode == "3055" and b.ndc == "007.64"
    d = b.to_dict()
    assert d["ccode"] == "3055" and d["ndc"] == "007.64"


def test_lookup_ccode_from_hanmoto_fallback():
    payload = (200, json.dumps([{
        "summary": {"title": "Dummy", "author": "A", "publisher": "P", "pubdate": "2020", "cover": ""},
        "onix": {},
        "hanmoto": {"ndccode": "913", "c_code": "0093"},
    }]))
    b = lookup(ISBN, fetch=fake({"openbd": payload}))
    assert b is not None and b.ccode == "0093" and b.ndc == "913"


def test_merge_fills_ccode():
    sparse = (200, json.dumps([{"summary": {
        "title": "吾輩は猫である", "author": "夏目漱石", "publisher": "", "pubdate": "", "cover": ""
    }}]))
    b = lookup(ISBN, fetch=fake({"openbd": sparse, "ndlsearch": (200, "<rss></rss>")}), merge=True)
    # no classifiers on sparse openBD
    assert b is not None and b.ccode == "" and b.title == "吾輩は猫である"


def test_existing_lookup_still_works_without_classifiers():
    plain = (200, json.dumps([{"summary": {
        "title": "吾輩は猫である", "author": "夏目漱石", "publisher": "岩波書店", "pubdate": "19900401", "cover": ""
    }}]))
    b = lookup(ISBN, fetch=fake({"openbd": plain}))
    assert b is not None and b.title == "吾輩は猫である" and b.ccode == "" and b.ndc == ""
