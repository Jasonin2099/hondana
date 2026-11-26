"""hondana — fold Japanese/CJK book metadata for matching, look up ISBNs."""
from .fold import fold, fold_steps, hira_to_kata, kata_to_hira, strip_reading_lines, to_shinjitai, width
from .isbn import find_isbns, hyphenate, is_valid, registration_group, to_isbn10, to_isbn13
from .export import dumps, to_bibtex, to_csl, to_ris
from .ccode import CCode, decode_ccode
from .ndc import NdcClass, ndc_class
from .lookup import Book, cached, lookup, lookup_many, search
from .dedupe import DuplicateGroup, DedupeResult, dedupe, dedupe_key
from .reimport import from_bibtex, from_csl, from_ris, loads

__version__ = "0.3.0"
__all__ = [
    "fold", "fold_steps", "kata_to_hira", "hira_to_kata", "to_shinjitai", "width", "strip_reading_lines",
    "is_valid", "to_isbn13", "to_isbn10", "find_isbns", "hyphenate", "registration_group",
    "Book", "lookup", "lookup_many", "search", "cached", "CCode", "decode_ccode",
    "NdcClass", "ndc_class",
    "dedupe", "dedupe_key", "DuplicateGroup", "DedupeResult",
    "to_bibtex", "to_ris", "to_csl", "dumps",
    "from_bibtex", "from_ris", "from_csl", "loads",
]
