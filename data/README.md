# Datasets

Two corpora, one per subdirectory. Notebooks name the dataset in their download cell, so
nothing here is fetched implicitly.

## `behr/`: Behr and KILZ technical data sheets

The main path, and the one demoed on screen.

| File | What |
|---|---|
| `Data_Resources_TDS.zip` | 137 product data sheets, the source PDFs |
| `Golden_Test_Data_DeepEval.csv` | golden question set, used by Labs 2, 3 and 4 |
| `Behr_all_products.xlsx` | product metadata used in Lab 3 |

The parsed and embedded version of this corpus is a release asset, not a file in the tree.

## `calhr/`: California state employee benefits

The alternate dataset, for attendees who want a domain closer to their own work. 20 PDFs,
186 pages, about 47,000 words, mirrored from CalHR so no lab ever fetches from the state's
site. `MANIFEST.md` lists the source URL, page count and word count per file.

The handbooks are what make this corpus interesting: they carry the tables that break naive
chunking. The two-page flyers add little retrieval difficulty. Five flipbook-only documents
on the CalHR site have downloads disabled and are not here.

`Golden_Test_Data_DeepEval.csv` is the golden question set, generated with the DeepEval
synthesizer and using the same columns as the Behr file. It has 116 rows, one question per
row, each drawn from a single chunk of context (`n_chunks_per_context` is 1 throughout) and
spread over 19 of the 20 PDFs. Columns: `input`, `expected_output`, `context`,
`context_length`, `evolutions`, `context_quality`, `synthetic_input_quality`, `source_file`,
plus `actual_output`, `retrieval_context` and `n_chunks_per_context`, which are empty or
constant in the saved file, and two leftover index columns (`Unnamed: 0`, `Unnamed: 0.1`).

Evolutions (how the synthesizer rewrote the question): Comparative 21, Constrained 19,
Hypothetical 18, Multi-context 18, Concretizing 16, Reasoning 13, In-Breadth 11.

`synthetic_input_quality`, which Lab 3 filters on: 1.0 on 57 rows, 0.8 on 50, 0.9 on 3, 0.7
on 3, and one row each at 0.6, 0.5 and 0.4. So 57 of the 116 rows have quality 1.0, and 60
have 0.9 or better.
