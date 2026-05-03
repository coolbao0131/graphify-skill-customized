# Cross-notebook routing (NotebookLM meta-graph)

When the user has multiple NotebookLM notebooks and asks a question that could span several, route via the meta-graph instead of guessing which notebook to query.

**Status**: experimental. Standalone Python in `experiments/notebooks/`. Not part of the official graphify package.

## When to use this recipe

User signals:
- "Ask all my notebooks about ..."
- "Which of my notebooks talks about ...?"
- "Compare what my notebooks say on ..."
- "I have notebooks about X, Y, Z — find which ones cover ..."
- Anything cross-notebook the user can't manually pre-filter

**Don't use** for: a single specified notebook (use `nlm notebook query <id>` directly), single-corpus codebase questions (use main `/graphify`).

## Prerequisites

1. The user must have `nlm` CLI authenticated (`nlm login`).
2. Customized graphify skill installed at `~/.claude/skills/graphify/` (this repo).
3. First-time: build the meta-graph (one-shot, ~30-90s for ~25 notebooks).

## Pipeline

```bash
PYTHON=$(which nlm | xargs -I{} dirname {} | xargs -I{} dirname {})/share/uv/tools/notebooklm-mcp-cli/bin/python
# Or just hardcoded for tony's machine:
PYTHON=/Users/tonyhuang/.local/share/uv/tools/notebooklm-mcp-cli/bin/python

cd ~/.claude/skills/graphify/experiments/notebooks

# Step 1: build (or update) the meta-graph
$PYTHON cli.py sync                     # full rebuild (~60s for 22 notebooks)
$PYTHON cli.py sync --update            # incremental — only refetch changed notebooks (~5s if nothing changed)

# Step 2: see routing decision (no LLM cost, instant)
$PYTHON cli.py route "<question>" -k 3

# Step 3: fan-out + get answers
$PYTHON cli.py ask "<question>" -k 3 --max-chars 2000
```

## How to interpret routing output

```json
{
  "routed_to": ["nb-id-1", "nb-id-2"],
  "scores": [0.31, 0.08],
  "reason": "high-confidence routing",
  "fallback": null,
  "labels": ["graphify+notebooklm research", "Second Brain"]
}
```

| `reason` / `fallback` | Meaning | What to do |
|---|---|---|
| `high-confidence routing` / `null` | Top-1 score notably higher than others | Run `ask`, expect 1-2 strong notebooks to answer |
| `low skew (...)` / `global_summary_after` | Multiple notebooks tied closely | Run `ask`, then synthesize the N answers yourself (or with another LLM call) — the question is broad |
| `max cosine X < threshold (R3AG null gate)` / `use_LLM_parametric` | No notebook matched well | **Don't run `ask`.** Tell the user: "no relevant notebook — answering from general knowledge" or ask them to rephrase |

## How to present `ask` results to the user

The output has per-notebook answers with citations. Format like:

> Routed to **2 notebooks** (high-confidence):
>
> **graphify+notebooklm integration deep research** (score 0.31, 168 sources):
> > GraphRAG differs from vector RAG in three ways: ... [cites 1, 2, 3]
>
> **Second Brain** (score 0.08, 70 sources):
> > In second-brain methodology, knowledge graphs serve as... [cites 4, 5]
>
> _Want me to synthesize these into a single answer?_ → if yes, ask Claude to merge the per-notebook answers.

For low-skew (`global_summary_after`) cases, **always** offer the synthesis — the user got fragmented answers across loosely-related notebooks and needs them woven together.

## Tuning knobs (don't change unless quality is bad)

- `-k 3` — fan-out width. **Stay ≤5** to avoid timeout (cross_notebook_query is parallel server-side: ~28s + 5s/extra notebook).
- `--null-threshold 0.10` — R³AG cutoff. Below this, no notebook is queried. Higher = stricter.
- `--skew-threshold 0.05` — SkewRoute boundary. Below this, fan-out is treated as low-confidence. Lower = more often labelled "broad".
- `--timeout 120` — per-notebook timeout. Recently-added notebooks (still indexing) may need 120-180s.

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `meta_graph not found` | `sync` never run | Run `cli.py sync` first |
| `0/N notebooks responded` (timeout) | NotebookLM busy or notebook still indexing | Wait 5min, retry; or `sync --skip-min 10` to skip recently-modified |
| All routing scores < 0.05 | Question vocabulary not covered by any summary | User needs richer notebooks, OR rephrase using terms that appear in notebook summaries |
| One notebook always wins regardless of question | Centroid dominated by very generic terms | Run `inspect` to see summaries; consider regenerating that notebook's NotebookLM-side summary |

## Architecture in one paragraph (if user asks how it works)

Each notebook becomes a meta-graph node carrying a centroid TF-IDF vector built from its summary + source titles (NotebookLM API). Routing is **zero-shot RouterRetriever-style**: query → cosine vs each centroid → top-k. Two fallback gates: **R³AG null gate** (max < threshold → don't query, let parent LLM use parametric knowledge) and **SkewRoute** (small top1-topK gap → mark as broad fan-out, suggest LLM merge after). Fan-out via NotebookLM's `cross_notebook_query` (parallel server-side, ~28s + 5s per extra notebook). All pure Python stdlib — no embeddings model, no training.

References: RouterRetriever, R³AG, RouteRAG/SkewRoute, MixRAG (papers in the user's `graphify+notebooklm integration deep research` notebook).
