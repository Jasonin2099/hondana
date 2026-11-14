from hondana import is_valid, to_isbn13, to_isbn10, find_isbns


def test_valid():
    assert is_valid("9784003101018")
    assert is_valid("4003101014")
    assert not is_valid("9784003101019")
    assert not is_valid("abc")


def test_convert():
    assert to_isbn13("4-00-310101-4") == "9784003101018"
    assert to_isbn10("9784003101018") == "4003101014"
    assert to_isbn13("9784003101019") == "9784003101018"  # repaired
    assert to_isbn13("9784003101019", strict=True) == ""
    assert to_isbn10("9784003101019") == "4003101014"  # repaired via 13
    assert to_isbn10("9784003101019", strict=True) == ""
    assert to_isbn10("4003101015") == "4003101014"  # ISBN-10 check repaired
    assert to_isbn10("4003101015", strict=True) == ""
    assert to_isbn10("9798000000000") == ""
    assert to_isbn10("9791032300824") == ""  # 979 has no ISBN-10
    assert to_isbn10("9791032300824", strict=True) == ""
    assert to_isbn13("") == to_isbn13(None) == ""
    assert to_isbn10("") == to_isbn10(None) == ""


def test_convert_roundtrip_and_hyphens():
    assert to_isbn10(to_isbn13("4-00-310101-4")) == "4003101014"
    assert to_isbn13(to_isbn10("978-4-00-310101-8")) == "9784003101018"
    assert to_isbn10("978-4-00-310101-8", strict=True) == "4003101014"
    assert to_isbn13("080442957X", strict=True) == "9780804429573"
    assert to_isbn10("9780804429573", strict=True) == "080442957X"


def test_x_check_digit():
    assert is_valid("080442957X")
    assert to_isbn13("080442957X") == "9780804429573"


def test_find():
    t = "ISBN 978-4-00-310101-8 と 4003101014、それに 1234567890"
    assert find_isbns(t) == ["9784003101018"]


def test_find_without_spaces_and_with_labels():
    for t in ["ISBN9784003101018", "ISBN-13:978-4-00-310101-8", "ISBN-10: 4-00-310101-4", "isbn4003101014", "(ISBN:4003101014)"]:
        assert find_isbns(t) == ["9784003101018"], t


def test_find_full_width_and_typographic_dashes():
    for t in ["９７８４００３１０１０１８", "978‐4‐00‐310101‐8", "978–4–00–310101–8", "978−4−00−310101−8", "ＩＳＢＮ４－００－３１０１０１－４"]:
        assert find_isbns(t) == ["9784003101018"], t


def test_hyphenate_japan_by_publisher_code_length():
    from hondana import hyphenate
    cases = {
        "4003101014": "978-4-00-310101-8",        # 岩波書店 (2 digits)
        "9784101010014": "978-4-10-101001-4",     # 新潮社
        "9784774112343": "978-4-7741-1234-3",     # 技術評論社 (4 digits)
        "9784873117782": "978-4-87311-778-2",     # オライリー・ジャパン (5 digits)
        "9784901234566": "978-4-901234-56-6",     # 6 digits
        "9784951234561": "978-4-9512345-6-1",     # 7 digits
    }
    for raw, want in cases.items():
        assert hyphenate(raw) == want, raw


def test_hyphenate_english_language_groups():
    from hondana import hyphenate
    cases = {
        "0131103628": "978-0-13-110362-7",        # 2-digit registrant
        "9780006479888": "978-0-00-647988-8",
        "9780804429573": "978-0-8044-2957-3",     # 4 digits
        "9781491946008": "978-1-4919-4600-8",     # 978-1, 4 digits
        "9781593279288": "978-1-59327-928-8",     # 978-1, 5 digits
    }
    for raw, want in cases.items():
        assert hyphenate(raw) == want, raw


def test_hyphenate_chinese_groups():
    from hondana import hyphenate
    cases = {
        "9787020002207": "978-7-02-000220-7",     # 978-7, 2-digit registrant
        "9787100000000": "978-7-100-00000-0",     # 3 digits
        "9787500000006": "978-7-5000-0000-6",     # 4 digits
        "9787800000003": "978-7-80000-000-3",     # 5 digits
        "9787900000002": "978-7-900000-00-2",     # 6 digits
        "9789570000009": "978-957-00-0000-9",     # Taiwan 957
        "9789574400003": "978-957-440-000-3",
        "9789579700009": "978-957-97000-0-9",
        "9789860000009": "978-986-00-0000-9",     # Taiwan 986
        "9789860600001": "978-986-06000-0-1",
        "9789861200002": "978-986-120-000-2",
        "9789868000001": "978-986-80000-0-1",
    }
    for raw, want in cases.items():
        assert hyphenate(raw) == want, raw


def test_hyphenate_other_groups_and_invalid():
    from hondana import hyphenate
    assert hyphenate("9783161484100") == "978-3-16-148410-0"   # German 978-3
    assert hyphenate("9782266111560") == "978-2-266-11156-0"   # French 978-2
    assert hyphenate("9791032300824") == "979-10-323-0082-4"   # France 979-10
    assert hyphenate("9784003101019") == ""   # bad check digit
    assert hyphenate("") == ""


def _check13(core12: str) -> str:
    return str((10 - sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core12)) % 10) % 10)


def test_hyphenate_korea_and_979():
    from hondana import hyphenate, is_valid
    # 978-89, 2-digit registrant (00-24)
    core = "978891234567"
    isbn = core + _check13(core)
    assert is_valid(isbn)
    assert hyphenate(isbn) == "978-89-12-34567-" + isbn[-1]
    # 978-89, 3-digit registrant (250-549)
    core = "978892501234"
    isbn = core + _check13(core)
    assert hyphenate(isbn) == "978-89-250-1234-" + isbn[-1]


def test_hyphenate_unassigned_range():
    from hondana import hyphenate, is_valid
    # 979-0 is not a registration group (length 0 in the EAN 979 prefix rules)
    core = "979012345678"
    isbn = core + _check13(core)
    assert is_valid(isbn)
    assert hyphenate(isbn) == ""


def test_parse_range_message_fixture(tmp_path):
    import importlib.util
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "scripts" / "update_isbn_ranges.py"
    spec = importlib.util.spec_from_file_location("update_isbn_ranges", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    xml = """<?xml version="1.0" encoding="utf-8"?>
<ISBNRangeMessage>
  <MessageSerialNumber>test-serial</MessageSerialNumber>
  <MessageDate>Sat, 14 Nov 2026 00:00:00 UTC</MessageDate>
  <EAN.UCCPrefixes>
    <EAN.UCC>
      <Prefix>978</Prefix>
      <Agency>International ISBN Agency</Agency>
      <Rules>
        <Rule><Range>0000000-5999999</Range><Length>1</Length></Rule>
        <Rule><Range>6000000-9999999</Range><Length>0</Length></Rule>
      </Rules>
    </EAN.UCC>
    <EAN.UCC>
      <Prefix>979</Prefix>
      <Agency>International ISBN Agency</Agency>
      <Rules>
        <Rule><Range>0000000-9999999</Range><Length>2</Length></Rule>
      </Rules>
    </EAN.UCC>
  </EAN.UCCPrefixes>
  <RegistrationGroups>
    <Group>
      <Prefix>978-4</Prefix>
      <Agency>Japan</Agency>
      <Rules>
        <Rule><Range>0000000-1999999</Range><Length>2</Length></Rule>
        <Rule><Range>2000000-9999999</Range><Length>0</Length></Rule>
      </Rules>
    </Group>
  </RegistrationGroups>
</ISBNRangeMessage>
"""
    date, serial, group_rules, registrant_rules = mod.parse_range_message(xml)
    assert date.startswith("Sat, 14 Nov 2026")
    assert serial == "test-serial"
    assert group_rules["978"][0] == ("0000000", "5999999", 1)
    assert registrant_rules["978-4"][0] == ("0000000", "1999999", 2)
    out = tmp_path / "_isbn_ranges.py"
    out.write_text(mod.render_module((date, serial, group_rules, registrant_rules)), encoding="utf-8")
    ns: dict = {}
    exec(out.read_text(encoding="utf-8"), ns)
    assert ns["MESSAGE_SERIAL"] == "test-serial"
    assert "978-4" in ns["REGISTRANT_RULES"]
