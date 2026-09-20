# Datasets

Two corpora, one per subdirectory. Notebooks name the dataset in their download cell, so
nothing here is fetched implicitly.

## `behr/` — Behr and KILZ technical data sheets

The main path, and the one demoed on screen.

| File | What |
|---|---|
| `Data_Resources_TDS.zip` | 137 product data sheets, the source PDFs |
| `Golden_Test_Data_DeepEval.csv` | golden question set, used by Labs 3 and 4 |
| `Behr_all_products.xlsx` | product metadata used in Lab 3 |

The parsed and embedded version of this corpus is a release asset, not a file in the tree.

## `calhr/` — California state employee benefits

The alternate dataset, for attendees who want a domain closer to their own work. 20 PDFs,
186 pages, about 47,000 words, mirrored from CalHR so no lab ever fetches from the state's
site. `MANIFEST.md` lists the source URL, page count and word count per file.

The handbooks are what make this corpus interesting: they carry the tables that break naive
chunking. The two-page flyers add little retrieval difficulty. Five flipbook-only documents
on the CalHR site have downloads disabled and are not here.

No golden set yet. It gets generated with the DeepEval synthesizer, matching the Behr file's
columns including `synthetic_input_quality`, which Lab 3 filters on.
