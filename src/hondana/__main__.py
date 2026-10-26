"""python -m hondana fold [--explain] [--small-kana] [--iteration-marks expand|drop] <text> | isbn <isbn>"""
import argparse
import json
import sys

from . import fold, fold_steps, lookup


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="hondana")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fold", help="print the matching key for some text")
    f.add_argument("text", nargs="+")
    f.add_argument("--explain", action="store_true", help="print the result of every step")
    f.add_argument("--small-kana", action="store_true", help="also fold small kana (ぁ→あ, っ→つ)")
    f.add_argument("--iteration-marks", choices=("expand", "drop"), help="handle 々 ゝ ゞ")
    i = sub.add_parser("isbn", help="look an ISBN up (openBD → NDL → Google Books → Open Library)")
    i.add_argument("isbn")
    a = p.parse_args(argv)
    if a.cmd == "fold":
        opts = {"small_kana": a.small_kana, "iteration_marks": a.iteration_marks}
        text = " ".join(a.text)
        if not a.explain:
            print(fold(text, **opts))
            return 0
        steps = fold_steps(text, **opts)
        w = max([len("input")] + [len(n) for n, _ in steps])
        print(f"{'input':<{w}}  {text}")
        prev = text
        for name, s in steps:
            print(f"{name:<{w}}  {s}" + ("" if s != prev else "  (no change)"))
            prev = s
        return 0
    b = lookup(a.isbn, on_error=lambda n, e: print(f"# {n}: {type(e).__name__}", file=sys.stderr))
    if b is None:
        print("not found", file=sys.stderr)
        return 1
    print(json.dumps(b.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
