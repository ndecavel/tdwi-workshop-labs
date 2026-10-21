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
    for name, i, rule, msg in problems:
        where = f"cell {i}" if i >= 0 else "notebook"
        print(f"FAIL [{rule}] {name}, {where}: {msg}")
    if problems:
        print(f"\n{len(problems)} problem(s) in {len(paths)} notebook(s).")
        return 1
    print(f"OK: {len(paths)} notebook(s) pass {len(RULES)} rules.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
