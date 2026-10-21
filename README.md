# TDWI hands-on RAG labs

Colab notebooks for the TDWI one-day workshop. Open a lab, give it your own OpenRouter key
(see [Keys](#keys)), and run.

**Labs 2 to 4 come in two versions.** Same notebook, two corpora: **Behr** is paint and
primer technical data sheets, **Benefits** is California state employee benefits handbooks.
Pick one and stay with it for the day. There is no switch inside a notebook on purpose:
changing dataset halfway leaves the old index and golden set in memory with no error.

| Lab | Behr (paint) | Benefits (CalHR) |
|---|---|---|
| 1. Prompting LLMs | [Lab_1_LLM_Prompting.ipynb](https://colab.research.google.com/github/ndecavel/tdwi-workshop-labs/blob/main/Labs/Lab_1_LLM_Prompting.ipynb) | same notebook, no dataset |
| 2. Naive RAG | [Lab_2_Naive_RAG_BEHR.ipynb](https://colab.research.google.com/github/ndecavel/tdwi-workshop-labs/blob/main/Labs/Lab_2_Naive_RAG_BEHR.ipynb) | [Lab_2_Naive_RAG_Benefits.ipynb](https://colab.research.google.com/github/ndecavel/tdwi-workshop-labs/blob/main/Labs/Lab_2_Naive_RAG_Benefits.ipynb) |
| 3. Improving RAG | [Lab_3_Improving_RAG_BEHR.ipynb](https://colab.research.google.com/github/ndecavel/tdwi-workshop-labs/blob/main/Labs/Lab_3_Improving_RAG_BEHR.ipynb) | [Lab_3_Improving_RAG_Benefits.ipynb](https://colab.research.google.com/github/ndecavel/tdwi-workshop-labs/blob/main/Labs/Lab_3_Improving_RAG_Benefits.ipynb) |
| 4. Scanning a RAG system for vulnerabilities | [Lab_4_Giskard_BEHR.ipynb](https://colab.research.google.com/github/ndecavel/tdwi-workshop-labs/blob/main/Labs/Lab_4_Giskard_BEHR.ipynb) | [Lab_4_Giskard_Benefits.ipynb](https://colab.research.google.com/github/ndecavel/tdwi-workshop-labs/blob/main/Labs/Lab_4_Giskard_Benefits.ipynb) |

Lab 4 runs as an instructor demo. Attendees do not run the full Giskard scan, which needs
Python 3.12, but they can run its leading-question pair and the system-prompt fix in Colab.

## What is here

```
Labs/         Lab 1, plus a Behr and a Benefits version of Labs 2 to 4. These notebooks
              are the source of truth and are edited directly
tools/        checks and the pin mover, see "Maintaining the labs" below
data/dataset_config.json   every setting the labs share, fetched by each notebook at runtime
data/behr/    137 Behr and KILZ technical data sheets, the golden question set, product metadata
data/calhr/   20 California state employee benefits PDFs, the alternate dataset
```

The Behr and Benefits twins are kept in step by hand and checked by
`tools/check_twins.py`. Commit notebooks with outputs stripped: install nbstripout and run
the two commands under [Maintaining the labs](#maintaining-the-labs). CI enforces it.

One subdirectory per dataset. `data/README.md` says what is in each and which is the main
path. Behr is the corpus demoed on screen; CalHR is there for attendees who want a domain
closer to their own work.

The parsed and embedded corpus is a **release asset**, not a file in the tree, because
80 people download it at once and release assets are CDN-served. See
[Releases](https://github.com/ndecavel/tdwi-workshop-labs/releases).

## Corpus

Each dataset ships one prepared corpus as a release asset, already embedded, so Lab 3 makes
no embedding calls at load time.

| | Behr | CalHR |
|---|---|---|
| File | `improved_nodes.parquet` | `calhr_nodes.parquet` |
| Chunks | 452 | 255 |
| Documents | 137 | 20 |
| Chunking | `SentenceSplitter(chunk_size=1024, chunk_overlap=200)` | `SentenceSplitter(chunk_size=384, chunk_overlap=96)` |
| Embedding model | `openrouter/openai/text-embedding-3-small` | same |
| Dimensions | 1536 | 1536 |

Columns (both files): `id`, `text`, `file_name`, `page_label`, `embedding` (float32),
`context` and `embedding_contextual`. `context` is a one or two sentence generated
description of where the chunk sits in its document, and `embedding_contextual` is the
embedding used for contextual retrieval (see Lab 3).

**Query-time embeddings must use the same model id.** A different one degrades dense
retrieval silently rather than raising.

## Keys

You need your own OpenRouter key: get one at https://openrouter.ai/keys. One key covers
chat, embeddings and the model Lab 4's Giskard scan uses.

The key cell near the top of each lab looks for the key in this order and stops at the
first one it finds:

1. `OPENROUTER_API_KEY` already set in the session.
2. Colab Secrets: the key icon in the left sidebar, a secret named `OPENROUTER_API_KEY`,
   with notebook access switched on. The easiest route, since it carries across every lab.
3. The workshop hub, which hands out keys only while a workshop is running.
4. A prompt asking you to paste it.

It prints where the key came from, never the key itself. No key is committed here. Do not
commit a notebook with a key pasted into it.

## How the labs score retrieval

Labs 2 and 3 measure one thing: whether retrieval hands the model the passage each golden
question was written from. No judge model scores answers. Both labs run one shared cell,
word for word, over every golden question the generator scored 1.0 (166 Behr, 57 Benefits),
and report four numbers over the top k chunks:

| | |
|---|---|
| hit@k | some chunk holds the passage (at least half of its 6-word phrases) |
| source hit@k | some chunk from the question's own file holds it |
| recall@k | the share of the passage the k chunks carry between them |
| MRR | 1 over the rank of the first chunk that holds it |

They are shown at k = 5, the setting every lab retrieves with, and at 10 and 20 with the
tokens each depth costs. A difference between two retrievers comes with a 95% interval from
resampling the questions. The only model call is one batched embedding of the questions.
The settings live under `retrieval_metrics` in `data/dataset_config.json`, and
`tools/check_notebooks.py` fails if the four copies of the cell ever differ.

## Pinned assets

The notebooks fetch their assets at a fixed commit or release tag rather than from `main`,
so an edit pushed here does not change anybody's run until a pin is moved.

| Pin | What it covers | Where |
|---|---|---|
| Commit | `data/dataset_config.json` and the source documents | 9 places across 6 notebooks |
| Same commit as the config | Lab 3's `table_exhibit.json` and `chunk_pages.json` | derived in the notebook from its config URL, so they move with it |
| Commit | the golden CSVs | 2 places in `data/dataset_config.json` |
| Release tag | the prepared corpus parquet files and the Behr scan report | the config and the notebooks |

Never edit these by hand. `tools/set_pin.py` moves them:

```
python tools/set_pin.py notebooks <sha> [--dry-run]
python tools/set_pin.py golden <sha> [--dry-run]
python tools/set_pin.py release <tag> [--dry-run]
```

It checks the commit exists, that every pinned path exists at that commit, and warns if the
commit has not been pushed (raw.githubusercontent.com only serves pushed commits).

**Two commits.** A commit cannot contain its own hash. So: commit the asset change (config,
documents, golden CSV) and push it, then run `set_pin.py` and commit the result. The second
commit points the notebooks at the first.

## Maintaining the labs

One-time setup in a fresh clone, so notebooks are stripped of outputs on commit:

```
pip install nbstripout
nbstripout --install --attributes .gitattributes
git config filter.nbstripout.extrakeys "cell.metadata.executionInfo cell.metadata.outputId"
```

| Tool | What it does |
|---|---|
| `tools/check_notebooks.py` | fails on saved outputs, execution records, em dashes, leftover placeholders, anything that looks like a key, and a retrieval-metric cell that is not identical across Labs 2 and 3 |
| `tools/check_twins.py` | fails when a Behr notebook and its Benefits twin differ outside the dataset-specific cells |
| `tools/set_pin.py` | moves the commit and release pins |
| `tools/build_table_exhibit.py` | builds `data/<dataset>/table_exhibit.json`, the one complex table Lab 3 shows three ways |
| `tools/build_chunk_pages.py` | builds `data/<dataset>/chunk_pages.json`, each corpus chunk's physical PDF page |

CI runs the first two on every push and pull request that touches `Labs/` or `tools/`.

Rule: add a setting to `data/dataset_config.json` before adding it to a notebook. The
notebooks read the config at the pinned commit, so a notebook that uses a setting the
pinned config lacks breaks for every attendee.

## Provenance

Supersedes `ndecavel/tdwi-llm`, which holds the 2025 run. Same source PDFs, same golden
set. The notebooks here fetch every asset from this repo, with no dependency on any other
account.
