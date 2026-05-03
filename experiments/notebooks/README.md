# meta-graph over NotebookLM notebooks (MVP)

Experimental graphify extension: turns N NotebookLM notebooks into a routable meta-graph. Given a question, picks the top-k most relevant notebooks via TF-IDF cosine, then fan-outs `cross_notebook_query` for grounded answers.

Status: **prototype**. Standalone in this `experiments/` folder; not wired into the main graphify skill.

## Why

NotebookLM has `cross_notebook_query` which fan-outs a question to N notebooks, but **you have to pick the N yourself**. With 23+ notebooks that's annoying and wasteful. This module picks the right ones automatically.

## Design

Based on routing-literature consultation via NotebookLM deep research:

| Decision | Choice | Source |
|---|---|---|
| Train router or zero-shot? | **Zero-shot** (no query log to train on) | RouterRetriever, RouteRAG/SkewRoute |
| Notebook representation | **Centroid TF-IDF** of summary + topics + source titles | RouterRetriever's "Pilot Embedding Library" |
| Routing algo | **Single-shot top-k cosine** (not iterative) | RouterRetriever |
| Gating mechanism | **Pure cosine, no MLP** | RouterRetriever showed trained gating *worse* for retrieval |
| Fallback | **R³AG null gate + SkewRoute low-skew detection** | R³AG, SkewRoute |
| Vectoriser | **Pure-stdlib char-4gram TF-IDF** | Handles Chinese + English without spaCy/jieba |

Why stdlib TF-IDF instead of `sentence-transformers`/OpenAI embeddings: 23 notebooks × ~1KB summary is tiny. Lighter, no model download, no API key, works for both Chinese and English notebooks.

## Files

- `meta_graph.py` — core: build / route / ask_meta. Pure functions over `notebooklm_tools` SDK.
- `cli.py` — argparse wrapper exposing `sync` / `route` / `ask` / `inspect` subcommands.

## Install

The MVP runs in the `nlm` CLI venv (already has `notebooklm_tools` SDK). No extra deps.

```bash
PYTHON=/Users/tonyhuang/.local/share/uv/tools/notebooklm-mcp-cli/bin/python
cd /path/to/this/dir
$PYTHON cli.py sync       # build meta-graph
```

## Usage

```bash
# Build / refresh meta-graph (writes graphify-out/notebooks-graph.json)
$PYTHON cli.py sync [--skip-min 5]

# Inspect what's in the graph
$PYTHON cli.py inspect

# See routing decision without actually querying
$PYTHON cli.py route "<question>" [-k 3] [--null-threshold 0.10] [--skew-threshold 0.05]

# Route + fan-out cross-notebook query
$PYTHON cli.py ask "<question>" [-k 3] [--timeout 120]
```

## Example

```bash
$ python cli.py route "How does GraphRAG differ from vector RAG?" -k 3
{
  "routed_to": ["ba7e5a84-...", "6dd9143d-..."],
  "scores": [0.312, 0.083],
  "reason": "high-confidence routing",
  "labels": ["graphify+notebooklm integration deep research", "Second Brain"]
}
```

Routing variants:

| Question type | Result |
|---|---|
| On-topic | `high-confidence routing`, top-1 score >> rest |
| Generic / cross-cutting | `low skew → fallback: global_summary_after` (broad fan-out, suggest LLM merge) |
| Off-topic / nonsense | `R3AG null gate → fallback: use_LLM_parametric` (no notebook queried) |

## Bench data (22 notebooks, ~1400 sources total)

- `cross_notebook_query` is parallel server-side: ~28s + 5s/extra notebook
- `batch_query` is sequential and less reliable — **don't use**
- Per-notebook timeout ~120s; recently-modified notebooks may need indexing time
- No rate limits hit at k=5 fan-out

## Summary freshness — when to use `--refresh-summaries`

By default, `sync` uses NotebookLM's `describe_notebook` API for the per-notebook summary. **describe IS regenerated live** on each call (we tested), so adding sources + re-syncing gets you a new summary automatically. BUT NotebookLM's describe has an internal **source budget** — for big notebooks it samples a subset, so the summary is biased toward whichever sources NotebookLM picked.

Empirical example on a 168-source notebook:

| Method | Summary length | Frameworks named |
|---|---|---|
| `describe_notebook` (default) | 1034 chars | 2 (NexusRAG, R³AG) |
| `chat.query "summarize all topics"` (`--refresh-summaries`) | 1746 chars | **16** (FastGraphRAG, GraphRAG, HippoRAG, HippoRAG2, HybridRAG, KET-RAG, KGP, LazyGraphRAG, LightRAG, MixRAG, R³AG, RAGRouter, RAPTOR, RouteRAG, RouterRetriever, StructRAG) |

**When to use** `--refresh-summaries`:
- Any notebook with >50 sources (describe sampling kicks in)
- After bulk source ingestion (e.g. you imported 50 papers at once)
- Periodic weekly refresh

**Cost**: ~70s per chunk of 5 notebooks via `cross_notebook_query`. 22 notebooks ≈ 6.5 min total. Safe to run as a `/schedule` weekly cron.

```bash
$PYTHON cli.py sync --refresh-summaries                       # full refresh
$PYTHON cli.py sync --update --refresh-summaries              # only refresh modified + force-refresh ALL summaries
$PYTHON cli.py sync --refresh-summaries --refresh-chunk-size 3  # smaller chunks if timeouts
```

Failed notebooks (transient timeouts) are auto-retried individually via `chat.query` after the batched pass.

## Known limitations

1. **`suggested_topics` always empty** in our test data — NotebookLM didn't auto-generate them. Centroid relies entirely on `summary` + `source_titles`. (Mitigated by `--refresh-summaries` since the live summary names topics inline.)
2. **No edge visualization yet** — graph.json is written but no HTML/wiki layer. graphify proper does this via `to_html`/`to_wiki`.
3. **No LLM-based answer synthesis** — when low-skew triggers `global_summary_after`, the user gets N separate answers; merging is left to caller.

## Future work

- Wire into main graphify SKILL as `/graphify sync-notebooks` / `/graphify route` / `/graphify ask-meta` (currently standalone)
- Use graphify's `to_html` / `to_wiki` to render the meta-graph for inspection
- Add `--update` incremental refresh based on `updated_at`
- Add LLM-merged answer synthesis for low-skew cases
- Optional: swap stdlib TF-IDF for `bge-m3` local embeddings (better quality, ~500MB model)
- Optional: add `shares_sources` edges for visualisation (currently only `semantically_similar_to`)

## References (from the deep-research notebook)

- RouterRetriever — training-free router via centroid embeddings
- R³AG — Null retriever gate ($R_0$) for low-confidence cases
- RouteRAG / SkewRoute — score-skewness-based fallback
- LazyGraphRAG — concept co-occurrence + graph expansion
- MixRAG — mixture-of-experts gating (for reference; we deliberately don't train)
