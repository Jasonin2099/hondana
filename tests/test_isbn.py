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
