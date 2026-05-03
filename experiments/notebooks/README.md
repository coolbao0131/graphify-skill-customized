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

## Known limitations (MVP)

1. **`suggested_topics` always empty** in our test data — NotebookLM didn't auto-generate them. Centroid relies entirely on `summary` + `source_titles`. May need richer node text if quality drops.
2. **`source_titles` count shows 0** in inspect output — `get_notebook` may not return sources field as expected; need to verify with `nlm source list <nb>` API.
3. **No notebook_title in cross_result** — the SDK returns notebook_id only. We could enrich on our side using routing's `labels`.
4. **No edge visualization yet** — graph.json is written but no HTML/wiki layer. graphify proper does this via `to_html`/`to_wiki`.
5. **No incremental update** — `sync` rebuilds from scratch. Should compare `updated_at` per notebook and skip unchanged.
6. **No LLM-based answer synthesis** — when low-skew triggers `global_summary_after`, the user gets N separate answers; merging is left to caller.

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
