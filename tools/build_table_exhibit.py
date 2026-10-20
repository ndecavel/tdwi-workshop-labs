#!/usr/bin/env python3
"""Build data/<dataset>/table_exhibit.json: one complex table shown three ways, for Lab 3.

Why. Lab 3 teaches that a table's meaning lives in its merged cells: which plan a column
belongs to, which rows a compliance code covers. A markdown pipe table cannot say "this
cell spans three columns", so the shipped corpus repeats it, drops it or smears it. The
exhibit puts the same printed table side by side as (1) PyMuPDF's plain text, (2) the
markdown chunk that actually shipped in the corpus, and (3) an HTML table with rowspan and
colspan, plus a picture of the printed original to compare against.

The HTML is NOT LlamaParse's own output (that raw parse is not available here). It is
rebuilt from PyMuPDF's table finder, which does detect spanning cells: every cell's
bounding box is mapped onto a grid of the distinct x and y boundaries, and a cell that
covers more than one grid step becomes a rowspan or colspan. Where the finder gets a
cell wrong, a small explicit correction in EXHIBITS (merge_cells) fixes it, and the
output's `html_source` says so.

The tables (one per dataset):
  behr   3190_TDS_US.pdf page 1, the compliance box (header across 4 columns, NGBS and
         MPI cells that span rows). Chunk 685f6a88-130c-4460-8177-1b9dee9d47c5.
  calhr  2027-benefit-summary-guide-active-state-employees.pdf physical page 16 (printed
         14), the PPO coverage table ("PPO PLANS" spans 3 columns).
         Chunk 00ca019b-f2cd-1075-32ac-f9f90228bec8.

Run it (from the repo root):
  python tools/build_table_exhibit.py --dataset behr
  python tools/build_table_exhibit.py --dataset calhr
  python tools/build_table_exhibit.py --dataset behr --pdfs path/to/pdfs --corpus path/to/nodes.parquet

--pdfs is a folder (searched recursively) or a .zip of PDFs. Defaults: data/calhr/ for
CalHR, data/behr/Data_Resources_TDS.zip for Behr. --corpus is a parquet file; the
default downloads the `corpus_url` named in data/dataset_config.json.

The output is a PINNED ASSET. Commit it and push, then move the notebook pins to that
commit with tools/set_pin.py (the two-commit rule in its docstring applies).
Needs pymupdf 1.28.2 (the version Lab 2 pins; other builds may extract different text)
and pandas (pyarrow).
"""
import argparse
import base64
import datetime
import html
import json
import re
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "data" / "dataset_config.json"

HTML_SOURCE = ("PyMuPDF find_tables (1.28.2), cell spans from its cell bounding boxes. "
               "LlamaParse's own HTML for this page was not available.")

# Everything that is specific to one table lives here, keyed to the page it was found on.
EXHIBITS = {
    "behr": {
        "source_pdf": "3190_TDS_US.pdf",
        "page": 1,
        "printed_page": None,
        "title": "Compliance box, BEHR COPPER FORCE No. 3190",
        "anchor": "COMPLIES WITH THE BELOW",   # text that sits inside the table
        "header_rows": 1,                      # rows drawn as the header band
        "chunk_id": "685f6a88-130c-4460-8177-1b9dee9d47c5",
        # The chunk's markdown is cut from the line starting md_start to the line starting md_end.
        "md_start": "## PRODUCT INFORMATION",
        "md_end": "| GREENGUARD",
        "merge_cells": [],
    },
    "calhr": {
        "source_pdf": "2027-benefit-summary-guide-active-state-employees.pdf",
        "page": 16,
        "printed_page": 14,
        "title": "PPO plan coverage, 2027 Benefits Summary for Active State Employees",
        "anchor": "Who Is Eligible?",
        "header_rows": 2,
        "chunk_id": "00ca019b-f2cd-1075-32ac-f9f90228bec8",
        "md_start": "||PPO PLANS",              # the chunk has no heading above the table
        "md_end": "|Calendar Year Maximum",
        # Correction: the top-left corner is one blank blue block printed across both header
        # rows, but find_tables reports it as two stacked cells. Merge them.
        "merge_cells": [[(54, 72, 138, 96), (54, 96, 138, 152)]],
    },
}

GRID_TOL = 1.5        # points: edges closer than this are the same grid line
CROP_MARGIN = 3       # points of page around the table in the picture
CROP_DPI = 150


# ---------- inputs ----------

def find_pdfs(source, workdir):
    """Map file name to path for every PDF under a folder or inside a zip."""
    source = Path(source)
    if source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as z:
            z.extractall(workdir)
        source = Path(workdir)
    return {p.name: p for p in sorted(source.rglob("*.pdf"))}


def load_chunk(dataset, corpus, chunk_id, workdir):
    """Return the text of one corpus chunk, downloading the config's corpus_url if needed."""
    if corpus is None:
        url = json.loads(CONFIG.read_text(encoding="utf-8"))["datasets"][dataset]["corpus_url"]
        corpus = Path(workdir) / "corpus.parquet"
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, corpus)
    df = pd.read_parquet(corpus, columns=["id", "text"])
    hit = df[df.id == chunk_id]
    if hit.empty:
        sys.exit(f"Chunk {chunk_id} is not in the corpus.")
    return hit.iloc[0].text


def default_pdfs(dataset):
    return ROOT / "data" / "calhr" if dataset == "calhr" else ROOT / "data" / "behr" / "Data_Resources_TDS.zip"


# ---------- the table grid ----------

def find_table(page, anchor):
    """The table whose box contains the anchor text."""
    spot = page.search_for(anchor)
    if not spot:
        sys.exit(f"Anchor text {anchor!r} not found on the page.")
    for t in page.find_tables().tables:
        if pymupdf.Rect(t.bbox).contains(spot[0]):
            return t
    sys.exit("No table found around the anchor text.")


def distinct_cells(table, merges):
    """Distinct cell rectangles, with the explicit merge corrections applied."""
    cells = []
    for c in table.cells:
        r = tuple(c)
        if not any(max(abs(a - b) for a, b in zip(r, o)) < 0.5 for o in cells):
            cells.append(r)
    for group in merges:
        found = [c for c in cells for g in group if max(abs(a - b) for a, b in zip(c, g)) < 1.5]
        if len(found) != len(group):
            sys.exit(f"Merge correction {group} no longer matches the table's cells.")
        cells = [c for c in cells if c not in found]
        cells.append((min(c[0] for c in found), min(c[1] for c in found),
                      max(c[2] for c in found), max(c[3] for c in found)))
    return cells


def boundaries(values):
    """Sorted distinct edge positions, merging values closer than GRID_TOL."""
    out = []
    for v in sorted(values):
        if out and v - out[-1] < GRID_TOL:
            continue
        out.append(v)
    return out


def index_of(edges, v):
    return min(range(len(edges)), key=lambda i: abs(edges[i] - v))


def place_cells(cells):
    """Map every cell to (row, col, rowspan, colspan) on the grid of distinct edges."""
    xs = boundaries([c[0] for c in cells] + [c[2] for c in cells])
    ys = boundaries([c[1] for c in cells] + [c[3] for c in cells])
    placed = []
    for c in cells:
        c0, c1 = index_of(xs, c[0]), index_of(xs, c[2])
        r0, r1 = index_of(ys, c[1]), index_of(ys, c[3])
        placed.append({"rect": c, "row": r0, "col": c0, "rowspan": r1 - r0, "colspan": c1 - c0})
    return placed, len(ys) - 1, len(xs) - 1


# ---------- cell text ----------

def cell_runs(page, rect):
    """Text of one cell as a list of lines; each line is a list of (text, is_superscript).

    Characters are taken by their centre point, so text from a neighbouring cell never
    leaks in. Superscripts (footnote marks) are kept as their own runs. Some headers are
    letter-spaced in the PDF ("P P O  P L A N S"); when most of a line's words are one
    character, the line is rebuilt from character positions so only real word gaps
    become spaces.
    """
    rect = pymupdf.Rect(rect)
    lines = []
    for block in page.get_text("rawdict", clip=rect)["blocks"]:
        for line in block.get("lines", []):
            chars = []
            for span in line["spans"]:
                sup = bool(span["flags"] & 1)
                for ch in span["chars"]:
                    b = ch["bbox"]
                    if rect.x0 <= (b[0] + b[2]) / 2 <= rect.x1 and rect.y0 <= (b[1] + b[3]) / 2 <= rect.y1:
                        chars.append((ch["c"], sup, b[0], b[2], span["size"]))
            if not chars:
                continue
            words = "".join(c for c, s, *_ in chars if not s).split()
            if len(words) >= 3 and sum(len(w) == 1 for w in words) >= 0.5 * len(words):
                chars = respace(chars)
            runs = []
            for c, sup, *_ in chars:
                if runs and runs[-1][1] == sup:
                    runs[-1][0] += c
                else:
                    runs.append([c, sup])
            runs = [(re.sub(r"\s+", "" if s else " ", t), s) for t, s in runs]
            runs = [(t.rstrip() if i + 1 < len(runs) and runs[i + 1][1] else t, s) for i, (t, s) in enumerate(runs)]
            runs = [(t, s) for t, s in runs if t.strip()]
            if runs:
                runs[0] = (runs[0][0].lstrip(), runs[0][1])
                runs[-1] = (runs[-1][0].rstrip(), runs[-1][1])
                lines.append(runs)
    return lines


def respace(chars):
    """Rebuild a letter-spaced line: a space only where the gap between glyphs is a word gap."""
    glyphs = [c for c in chars if not c[0].isspace()]
    out = []
    for i, (c, sup, x0, x1, size) in enumerate(glyphs):
        if i and x0 - glyphs[i - 1][3] > 0.3 * size:
            out.append((" ", False, x0, x0, size))
        out.append((c, sup, x0, x1, size))
    return out


def cell_text(lines):
    return " ".join("".join(t for t, _ in line) for line in lines).strip()


def cell_html(lines):
    """Lines joined with <br>, superscript runs wrapped in <sup>, text escaped."""
    out = []
    for line in lines:
        out.append("".join(f"<sup>{html.escape(t)}</sup>" if s else html.escape(t) for t, s in line))
    return "<br>".join(out)


# ---------- the three views ----------

def build_html(page, placed, nrows, ncols, header_rows):
    by_pos = {(p["row"], p["col"]): p for p in placed}
    covered = set()
    rows = []
    for r in range(nrows):
        tds = []
        for c in range(ncols):
            if (r, c) in covered:
                continue
            p = by_pos.get((r, c))
            if p is None:
                sys.exit(f"Grid position row {r}, column {c} has no cell; the table finder missed one.")
            for rr in range(r, r + p["rowspan"]):
                for cc in range(c, c + p["colspan"]):
                    covered.add((rr, cc))
            lines = cell_runs(page, p["rect"])
            p["text"] = cell_text(lines)
            tag = "th" if r < header_rows or p["colspan"] == ncols else "td"
            attrs = ""
            if p["rowspan"] > 1:
                attrs += f' rowspan="{p["rowspan"]}"'
            if p["colspan"] > 1:
                attrs += f' colspan="{p["colspan"]}"'
            tds.append(f"<{tag}{attrs}>{cell_html(lines)}</{tag}>")
        rows.append("  <tr>" + "".join(tds) + "</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def trim_markdown(text, start, end):
    """Verbatim lines from the one starting with `start` to the last one starting with `end`."""
    lines = text.split("\n")
    first = next((i for i, l in enumerate(lines) if l.startswith(start)), None)
    last = max((i for i, l in enumerate(lines) if l.startswith(end)), default=None)
    if first is None or last is None or last < first:
        sys.exit(f"Could not find {start!r} .. {end!r} in the chunk.")
    return "\n".join(lines[first:last + 1])


def build(dataset, pdfs, corpus, workdir):
    ex = EXHIBITS[dataset]
    if ex["source_pdf"] not in pdfs:
        sys.exit(f"{ex['source_pdf']} not found in the PDFs given.")
    with pymupdf.open(pdfs[ex["source_pdf"]]) as doc:
        page = doc[ex["page"] - 1]
        table = find_table(page, ex["anchor"])
        cells = distinct_cells(table, ex["merge_cells"])
        placed, nrows, ncols = place_cells(cells)
        table_html = build_html(page, placed, nrows, ncols, ex["header_rows"])
        box = pymupdf.Rect(min(c[0] for c in cells), min(c[1] for c in cells),
                           max(c[2] for c in cells), max(c[3] for c in cells))
        pix = page.get_pixmap(dpi=CROP_DPI, clip=(box + (-CROP_MARGIN, -CROP_MARGIN, CROP_MARGIN, CROP_MARGIN)) & page.rect)
        png = base64.b64encode(pix.tobytes("png")).decode("ascii")
        pdf_text = page.get_text("text", clip=box)
    chunk = load_chunk(dataset, corpus, ex["chunk_id"], workdir)
    spans = [{"text": p["text"], "rowspan": p["rowspan"], "colspan": p["colspan"]}
             for p in sorted(placed, key=lambda p: (p["row"], p["col"]))
             if p["rowspan"] > 1 or p["colspan"] > 1]
    html_source = HTML_SOURCE
    if ex["merge_cells"]:
        html_source += (f" {len(ex['merge_cells'])} cell merge correction(s) applied by hand in the tool "
                        "where the finder split one printed cell in two: the blank top-left corner "
                        "block, printed once across both header rows.")
    return {
        "dataset": dataset,
        "source_pdf": ex["source_pdf"],
        "page": ex["page"],
        "printed_page": ex["printed_page"],
        "title": ex["title"],
        "image_png_b64": png,
        "pymupdf_text": pdf_text,
        "markdown": trim_markdown(chunk, ex["md_start"], ex["md_end"]),
        "markdown_chunk_id": ex["chunk_id"],
        "html": table_html,
        "html_source": html_source,
        "spans": spans,
        "built": datetime.date.today().isoformat(),
        "tool": "tools/build_table_exhibit.py",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dataset", required=True, choices=sorted(EXHIBITS))
    ap.add_argument("--pdfs", help="folder or .zip of the source PDFs")
    ap.add_argument("--corpus", help="corpus parquet (default: download the config's corpus_url)")
    ap.add_argument("--out", help="output path (default data/<dataset>/table_exhibit.json)")
    a = ap.parse_args()
    out = Path(a.out) if a.out else ROOT / "data" / a.dataset / "table_exhibit.json"
    if pymupdf.__version__ != "1.28.2":
        print(f"WARNING: pymupdf {pymupdf.__version__}, Lab 2 pins 1.28.2; the text may differ.")
    with tempfile.TemporaryDirectory() as work:
        pdfs = find_pdfs(a.pdfs or default_pdfs(a.dataset), work)
        result = build(a.dataset, pdfs, a.corpus, work)
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{out}: {out.stat().st_size} bytes, {len(result['spans'])} spanning cells")
    for s in result["spans"]:
        print(f"  rowspan={s['rowspan']} colspan={s['colspan']} {s['text']!r}")


if __name__ == "__main__":
    main()
