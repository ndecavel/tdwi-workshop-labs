#!/usr/bin/env python3
"""Build data/<dataset>/chunk_pages.json: which physical PDF page each corpus chunk came from.

Why. The corpus carries a `page_label` per chunk, but it is not the physical page. For
Behr it is the physical page or a range ("1-2"). For CalHR it is the number PRINTED on
the page, which differs from the physical page in the long documents (a cover and a
table of contents push every printed number down). Lab 3's small-to-big cell groups
chunks "from the same page", so it needs the physical page, and it needs it without
shipping any text. This file is that mapping: ids and page numbers only.

How. Every chunk is normalised (tags, markdown punctuation and case removed) and cut
into 6-word shingles. Every page of its source PDF, read by PyMuPDF, is cut the same way.
The chunk goes to the page that holds the largest share of its shingles. If that share is
under 30%, a fallback compares single words and accepts a page holding 80% of them;
otherwise the chunk is left unplaced (null). A chunk that has at least 10% of its
shingles on some other page also gets an entry under "spans", listing every page it
touches, because a table or a paragraph that runs across a page break belongs to both.

Output:
  {"dataset", "corpus", "method", "pages": {chunk_id: page or null},
   "spans": {chunk_id: [pages]}, "unplaced": [chunk_id, ...]}

Run it (from the repo root):
  python tools/build_chunk_pages.py --dataset behr
  python tools/build_chunk_pages.py --dataset calhr
  python tools/build_chunk_pages.py --dataset behr --pdfs path/to/pdfs --corpus path/to/nodes.parquet

--pdfs is a folder (searched recursively) or a .zip of PDFs. Defaults: data/calhr/ for
CalHR, data/behr/Data_Resources_TDS.zip for Behr. --corpus is a parquet file; the
default downloads the `corpus_url` named in data/dataset_config.json.

The output is a PINNED ASSET. Commit it and push, then move the notebook pins to that
commit with tools/set_pin.py (the two-commit rule in its docstring applies).
Needs pymupdf and pandas (pyarrow); the corpus build used pymupdf 1.28.2.
"""
import argparse
import collections
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

SHINGLE = 6          # words per shingle
PLACE_MIN = 0.30     # share of a chunk's shingles a page must hold to claim it
UNIGRAM_MIN = 0.80   # fallback: share of a chunk's words a page must hold
SPAN_MIN = 0.10      # share of shingles on another page that makes a chunk "span"

METHOD = (
    "Each chunk and each PDF page (PyMuPDF text) is normalised (HTML tags, markdown "
    "punctuation, case and other punctuation removed) and cut into 6-word shingles. A "
    "chunk is placed on the page that holds the largest share of its shingles, if that "
    "share is at least 30%. Otherwise a fallback compares single words and accepts a page "
    "that holds at least 80% of them; a chunk neither test places is listed under "
    "'unplaced' with a null page (for example a PDF with no text layer). A chunk with at "
    "least 10% of its shingles on another page is listed under 'spans' with every page it "
    "touches. Pages are physical, 1-based, and are not the page_label column, which for "
    "CalHR is the number printed on the page."
)


def normalise(text):
    """Lower-case words with tags, ligatures and markdown punctuation removed."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = re.sub(r"[#*_|`>\-]+", " ", text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().split()


def shingles(words):
    return {" ".join(words[i:i + SHINGLE]) for i in range(max(0, len(words) - SHINGLE + 1))}


def find_pdfs(source, workdir):
    """Map file name to path for every PDF under a folder or inside a zip."""
    source = Path(source)
    if source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as z:
            z.extractall(workdir)
        source = Path(workdir)
    return {p.name: p for p in sorted(source.rglob("*.pdf"))}


def load_corpus(dataset, corpus, workdir):
    """Return (dataframe, corpus_url). Downloads the config's corpus_url when no file is given."""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))["datasets"][dataset]
    url = cfg["corpus_url"]
    if corpus is None:
        corpus = Path(workdir) / "corpus.parquet"
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, corpus)
    return pd.read_parquet(corpus, columns=["id", "text", "file_name"]), url


def default_pdfs(dataset):
    return ROOT / "data" / "calhr" if dataset == "calhr" else ROOT / "data" / "behr" / "Data_Resources_TDS.zip"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dataset", required=True, choices=["behr", "calhr"])
    ap.add_argument("--pdfs", help="folder or .zip of the source PDFs")
    ap.add_argument("--corpus", help="corpus parquet (default: download the config's corpus_url)")
    ap.add_argument("--out", help="output path (default data/<dataset>/chunk_pages.json)")
    a = ap.parse_args()
    out = Path(a.out) if a.out else ROOT / "data" / a.dataset / "chunk_pages.json"

    with tempfile.TemporaryDirectory() as work:
        pdfs = find_pdfs(a.pdfs or default_pdfs(a.dataset), work)
        corpus, corpus_url = load_corpus(a.dataset, a.corpus, work)

        missing = sorted(set(corpus.file_name) - set(pdfs))
        if missing:
            sys.exit(f"No PDF found for: {', '.join(missing)}")

        # One shingle set per page, read once per PDF.
        page_sets, page_words = {}, {}
        for name in sorted(set(corpus.file_name)):
            with pymupdf.open(pdfs[name]) as doc:
                words = [normalise(page.get_text()) for page in doc]
            page_words[name] = [collections.Counter(w) for w in words]
            page_sets[name] = [shingles(w) for w in words]

        pages, spans, unplaced = {}, {}, []
        for row in corpus.itertuples():
            words = normalise(row.text)
            chunk = shingles(words)
            n = max(len(chunk), 1)
            sets = page_sets[row.file_name]
            share = [len(chunk & s) / n for s in sets]
            best = max(range(len(sets)), key=share.__getitem__)  # first page wins a tie
            page = best + 1 if share[best] >= PLACE_MIN else None
            if page is None:
                # Fallback for chunks too short or too reshaped to share 6-word runs.
                counts = collections.Counter(words)
                total = sum(counts.values()) or 1
                overlap = [sum(min(v, pc[w]) for w, v in counts.items()) / total
                           for pc in page_words[row.file_name]]
                ubest = max(range(len(overlap)), key=overlap.__getitem__)
                if overlap[ubest] >= UNIGRAM_MIN:
                    page = ubest + 1
            pages[row.id] = page
            if page is None:
                unplaced.append(row.id)
                continue
            rest = chunk - sets[best]
            other = [i + 1 for i, s in enumerate(sets)
                     if i != best and len(rest & s) / n >= SPAN_MIN]
            if other:
                spans[row.id] = sorted({page, *other})

    result = {"dataset": a.dataset, "corpus": corpus_url, "method": METHOD,
              "pages": pages, "spans": spans, "unplaced": unplaced}
    out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(f"{out}: {len(pages)} chunks, {len(pages) - len(unplaced)} placed, "
          f"{len(spans)} spanning, {len(unplaced)} unplaced")


if __name__ == "__main__":
    main()
