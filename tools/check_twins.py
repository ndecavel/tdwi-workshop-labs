#!/usr/bin/env python3
"""Check that each Behr notebook and its Benefits twin differ only where they should.

The twins are edited by hand and kept in step by hand. This compares them cell by
cell and fails on:
  - a different number of cells
  - a different cell type at the same index
  - any source difference in a cell that is not allow-listed

A cell is allow-listed (dataset-specific, allowed to differ) in either of two ways:

  1. By index: the ALLOWED dict below, one entry per lab, 0-based cell indexes.
     Update it when cells move.
  2. By marker, which survives cells moving: put the line
         # twin: dataset-specific            (code cell)
         <!-- twin: dataset-specific -->     (markdown cell)
     in BOTH twins. The marker lines themselves are ignored when comparing.

Options:
  --show   print a unified diff of every differing cell, allow-listed ones too
           (for review)

Warns, without failing, when an allow-listed cell is now identical (the list is
stale) or when only one twin carries a marker.

Usage: python tools/check_twins.py [--show]
"""
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABS = ROOT / "Labs"

# lab -> (Behr file, Benefits file, allow-listed cell indexes)
ALLOWED = {
    "Lab 2": ("Lab_2_Naive_RAG_BEHR.ipynb", "Lab_2_Naive_RAG_Benefits.ipynb",
              {0, 4, 5, 6, 12, 14, 16, 19, 20, 34, 45}),
    "Lab 3": ("Lab_3_Improving_RAG_BEHR.ipynb", "Lab_3_Improving_RAG_Benefits.ipynb",
              {0, 3, 6, 8, 10, 11, 14, 15, 17, 20, 31, 32, 33, 37, 42, 51}),
    "Lab 4": ("Lab_4_Giskard_BEHR.ipynb", "Lab_4_Giskard_Benefits.ipynb",
              {0, 4, 8, 10, 12, 16, 17}),
}

MARKERS = {"code": "# twin: dataset-specific", "markdown": "<!-- twin: dataset-specific -->"}


def load(name):
    return json.loads((LABS / name).read_text(encoding="utf-8"))["cells"]


def text(cell):
    s = cell.get("source", "")
    return s if isinstance(s, str) else "".join(s)


def has_marker(cell):
    marker = MARKERS.get(cell.get("cell_type"))
    return marker is not None and any(ln.strip() == marker for ln in text(cell).split("\n"))


def comparable(cell):
    marker = MARKERS.get(cell.get("cell_type"))
    return "\n".join(ln for ln in text(cell).split("\n") if ln.strip() != marker)


def diff(a, b, i):
    return "".join(difflib.unified_diff(
        comparable(a).splitlines(True), comparable(b).splitlines(True),
        f"behr[{i}]", f"benefits[{i}]"))


def check_lab(lab, behr, benefits, allowed, show):
    fails, warns = [], []
    a, b = load(behr), load(benefits)
    if len(a) != len(b):
        fails.append(f"{lab}: cell counts differ ({behr}: {len(a)}, {benefits}: {len(b)})")
    for i, (ca, cb) in enumerate(zip(a, b)):
        if ca.get("cell_type") != cb.get("cell_type"):
            fails.append(f"{lab} cell {i}: type differs ({ca.get('cell_type')} vs {cb.get('cell_type')})")
            continue
        if has_marker(ca) != has_marker(cb):
            warns.append(f"{lab} cell {i}: 'twin: dataset-specific' marker is in only one twin")
        marked = has_marker(ca) and has_marker(cb)
        differs = comparable(ca) != comparable(cb)
        listed = i in allowed or marked
        if differs and show:
            print(f"--- {lab} cell {i} ({'allowed' if listed else 'NOT ALLOWED'}) ---")
            print(diff(ca, cb, i))
        if differs and not listed:
            fails.append(f"{lab} cell {i}: twins differ and the cell is not allow-listed")
        if not differs and listed:
            warns.append(f"{lab} cell {i}: allow-listed but identical in both twins (stale entry?)")
    return fails, warns


def main(argv):
    show = "--show" in argv
    fails, warns = [], []
    for lab, (behr, benefits, allowed) in ALLOWED.items():
        f, w = check_lab(lab, behr, benefits, allowed, show)
        fails += f
        warns += w
    for w in warns:
        print("WARN", w)
    for f in fails:
        print("FAIL", f)
    if fails:
        print(f"\n{len(fails)} twin difference(s) not covered by the allow-list.")
        return 1
    print(f"OK: {len(ALLOWED)} twin pairs match outside their allow-lists ({len(warns)} warning(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
