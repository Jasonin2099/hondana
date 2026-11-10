"""Run every ```python block in docs/*.md so the examples can't rot."""
import pathlib
import re

import pytest

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"
BLOCK = re.compile(r"^```python\n(.*?)^```", re.S | re.M)


def _blocks():
    for md in sorted(DOCS.glob("*.md")):
        for i, m in enumerate(BLOCK.finditer(md.read_text(encoding="utf-8"))):
            yield pytest.param(m.group(1), id=f"{md.stem}-{i}")


@pytest.mark.parametrize("code", list(_blocks()))
def test_doc_example_runs(code):
    exec(compile(code, "<doc>", "exec"), {"__name__": "__doc_example__"})


def test_recipes_has_examples():
    assert len([p for p in _blocks() if p.id.startswith("recipes-")]) >= 4


def test_cli_find_on_reference_text(capsys):
    from hondana.__main__ import main
    rc = main(["isbn", "--find", "ISBN 4-00-310101-4 / ISBN978-0-14-044913-6"])
    assert rc == 0
    assert capsys.readouterr().out.split() == ["978-4-00-310101-8", "978-0-14-044913-6"]
