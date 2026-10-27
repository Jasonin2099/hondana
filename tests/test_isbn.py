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
    assert to_isbn10("9798000000000") == ""


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


def test_hyphenate_other_groups_and_invalid():
    from hondana import hyphenate
    assert hyphenate("9780804429573") == ""   # English-language group, not covered yet
    assert hyphenate("9784003101019") == ""   # bad check digit
    assert hyphenate("") == ""
