#!/usr/bin/env python3
"""Fail when a notebook in Labs/ breaks a shipping rule. Run by CI.

Rules (each is a small function below; add one to RULES to extend):

  outputs      no saved outputs, no execution counts, no Colab execution records
  em_dash      no U+2014 in any markdown or code cell (attendees read both)
  banned       "RFR" and "Ten questions" must not appear in a markdown cell
  key          nothing that looks like an OpenRouter key (sk-or- plus 10 word chars)
  placeholder  no leftover {{MEASURE: ...}} placeholder

Each rule takes (nb_name, cells) and yields (cell_index, message). A cell index
of -1 means the notebook as a whole.

One more check runs across notebooks, when every notebook in Labs/ is checked:

  shared       a cell that Labs 2 and 3 must carry word for word (the retrieval
               metrics) appears exactly once in each of those notebooks, and every
               copy is identical, so a score means the same thing in both labs

Usage: python tools/check_notebooks.py [notebook ...]   (default: Labs/*.ipynb)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EM_DASH = "\u2014"
KEY_RE = re.compile(r"sk-or-\w{10,}")
BANNED_IN_MARKDOWN = ("RFR", "Ten questions")
EXECUTION_META = ("executionInfo", "outputId")


def source(cell):
    s = cell.get("source", "")
    return s if isinstance(s, str) else "".join(s)


def rule_outputs(name, cells):
    for i, c in enumerate(cells):
        if c.get("cell_type") != "code":
            continue
        if c.get("outputs"):
            yield i, f"code cell has {len(c['outputs'])} saved output(s)"
        if c.get("execution_count") is not None:
            yield i, f"code cell has execution_count {c['execution_count']}"
        for key in EXECUTION_META:
            if key in c.get("metadata", {}):
                yield i, f"cell metadata has Colab execution record '{key}'"


def rule_em_dash(name, cells):
    for i, c in enumerate(cells):
        if c.get("cell_type") in ("markdown", "code") and EM_DASH in source(c):
            yield i, f"{c['cell_type']} cell contains an em dash (U+2014)"


def rule_banned(name, cells):
    for i, c in enumerate(cells):
        if c.get("cell_type") != "markdown":
            continue
        for word in BANNED_IN_MARKDOWN:
            if word in source(c):
                yield i, f'markdown cell contains "{word}"'


def rule_key(name, cells):
    for i, c in enumerate(cells):
        # Search the raw JSON of the cell so outputs and metadata are covered too.
        if KEY_RE.search(json.dumps(c, ensure_ascii=False)):
            yield i, "looks like an OpenRouter key (sk-or-...); value not shown"


def rule_placeholder(name, cells):
    for i, c in enumerate(cells):
        if "{{MEASURE:" in source(c):
            yield i, "leftover {{MEASURE: ...}} placeholder"


RULES = [rule_outputs, rule_em_dash, rule_banned, rule_key, rule_placeholder]

# A shared cell is found by its first line. name -> (first line, notebooks that must carry it)
SHARED_CELLS = {
    "retrieval metrics": ("## Retrieval metrics. Lab 2 and Lab 3 run this same cell, word for word",
                          ("Lab_2_*.ipynb", "Lab_3_*.ipynb")),
}


def check_shared():
    problems = []
    for name, (first_line, patterns) in SHARED_CELLS.items():
        copies = {}
        for pattern in patterns:
            for path in sorted((ROOT / "Labs").glob(pattern)):
                cells = json.loads(path.read_text(encoding="utf-8")).get("cells", [])
                found = [(i, source(c)) for i, c in enumerate(cells)
                         if c.get("cell_type") == "code" and source(c).startswith(first_line)]
                if len(found) != 1:
                    problems.append((path.name, -1, "shared", f"has {len(found)} copies of the {name} cell, needs 1"))
                else:
                    copies[path.name] = found[0]
        if len({text for _, text in copies.values()}) > 1:
            reference = next(iter(copies))
            for nb_name, (i, text) in copies.items():
                if text != copies[reference][1]:
                    problems.append((nb_name, i, "shared", f"the {name} cell differs from the copy in {reference}"))
    return problems


def check(path):
    nb = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    for rule in RULES:
        for i, msg in rule(path.name, nb.get("cells", [])):
            problems.append((path.name, i, rule.__name__[5:], msg))
    if KEY_RE.search(json.dumps(nb.get("metadata", {}))):
        problems.append((path.name, -1, "key", "notebook metadata looks like a key"))
    return problems


def main(argv):
    paths = [Path(a) for a in argv] or sorted((ROOT / "Labs").glob("*.ipynb"))
    problems = []
    for p in paths:
        problems += check(p)
    if not argv:
        problems += check_shared()
    for name, i, rule, msg in problems:
        where = f"cell {i}" if i >= 0 else "notebook"
        print(f"FAIL [{rule}] {name}, {where}: {msg}")
    if problems:
        print(f"\n{len(problems)} problem(s) in {len(paths)} notebook(s).")
        return 1
    shared = " and the shared-cell check" if not argv else ""
    print(f"OK: {len(paths)} notebook(s) pass {len(RULES)} rules{shared}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
