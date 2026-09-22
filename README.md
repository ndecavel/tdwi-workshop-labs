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
| 4. Evaluating with Giskard | [Lab_4_Giskard_BEHR.ipynb](https://colab.research.google.com/github/ndecavel/tdwi-workshop-labs/blob/main/Labs/Lab_4_Giskard_BEHR.ipynb) | [Lab_4_Giskard_Benefits.ipynb](https://colab.research.google.com/github/ndecavel/tdwi-workshop-labs/blob/main/Labs/Lab_4_Giskard_Benefits.ipynb) |

Lab 4 runs as an instructor demo. Attendees do not run the full Giskard scan.

## What is here

```
Labs/         Lab 1, plus a Behr and a Benefits version of Labs 2 to 4, plus the
              chunking app Lab 2 launches. GENERATED: edit templates/ in the
              authoring repo and run scripts/build_notebooks.py, never these files
data/dataset_config.json   every setting the labs share, fetched by each notebook at runtime
data/behr/    137 Behr and KILZ technical data sheets, the golden question set, product metadata
data/calhr/   20 California state employee benefits PDFs, the alternate dataset
```

One subdirectory per dataset. `data/README.md` says what is in each and which is the main
path. Behr is the corpus demoed on screen; CalHR is there for attendees who want a domain
closer to their own work.

The parsed and embedded corpus is a **release asset**, not a file in the tree, because
80 people download it at once and release assets are CDN-served. See
[Releases](https://github.com/ndecavel/tdwi-workshop-labs/releases).

## Corpus

`improved_nodes.parquet` is 452 chunks over the 137 data sheets, already embedded, so Lab 3
makes no embedding calls at load time.

| | |
|---|---|
| Chunking | `SentenceSplitter(chunk_size=1024, chunk_overlap=200)` |
| Embedding model | `openrouter/openai/text-embedding-3-small` |
| Dimensions | 1536 |

Columns: `id`, `text`, `file_name`, `page_label`, `embedding` (float32).

**Query-time embeddings must use the same model id.** A different one degrades dense
retrieval silently rather than raising.

## Keys

You need your own OpenRouter key: get one at https://openrouter.ai/keys. One key covers
chat, embeddings and the evaluation judge.

The key cell near the top of each lab looks for the key in this order and stops at the
first one it finds:

1. `OPENROUTER_API_KEY` already set in the session.
2. Colab Secrets: the key icon in the left sidebar, a secret named `OPENROUTER_API_KEY`,
   with notebook access switched on. The easiest route, since it carries across every lab.
3. The workshop hub, which hands out keys only while a workshop is running.
4. A prompt asking you to paste it.

It prints where the key came from, never the key itself. No key is committed here. Do not
commit a notebook with a key pasted into it.

## Pinned assets

The notebooks fetch `data/dataset_config.json`, the golden sets and the source documents
at a fixed commit rather than from `main`, and the prepared corpus from a release tag. An
edit pushed here does not change anybody's run until the pinned commit in the authoring
repo's `templates/` is moved to it and the notebooks are rebuilt.

## Provenance

Supersedes `ndecavel/tdwi-llm`, which holds the 2025 run. Same source PDFs, same golden
set. The notebooks here fetch every asset from this repo, with no dependency on any other
account.
