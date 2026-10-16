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


