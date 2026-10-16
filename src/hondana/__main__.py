"""python -m hondana fold <text> | isbn <isbn>"""
import argparse
import json
import sys

from . import fold, lookup


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="hondana")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fold", help="print the matching key for some text")
    f.add_argument("text", nargs="+")
    i = sub.add_parser("isbn", help="look an ISBN up (openBD → NDL → Google Books → Open Library)")
    i.add_argument("isbn")
    a = p.parse_args(argv)
    if a.cmd == "fold":
        print(fold(" ".join(a.text)))
        return 0
    b = lookup(a.isbn, on_error=lambda n, e: print(f"# {n}: {type(e).__name__}", file=sys.stderr))
    if b is None:
        print("not found", file=sys.stderr)
        return 1
    print(json.dumps(b.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
