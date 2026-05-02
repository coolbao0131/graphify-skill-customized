# How to read GRAPH_REPORT.md and surface the right things

After a graphify run, you have `graphify-out/GRAPH_REPORT.md`. SKILL Step 9 says paste God Nodes / Surprising Connections / Suggested Questions sections and offer one follow-up question. This recipe expands on _how_ to pick.

## Report structure (what's in there)

```
## Corpus Check          — warning if corpus is small
## Summary               — node/edge counts, EXTRACTED/INFERRED ratio, token cost
## God Nodes             — top-N most connected (sorted by degree)
## Surprising Connections — cross-community edges, often INFERRED
## Hyperedges            — group relationships (3+ nodes)
## Communities           — each with cohesion score + node list
## Knowledge Gaps        — isolated nodes, thin communities
## Suggested Questions   — generated from graph topology
```

## What to paste vs summarize

**Paste verbatim** (these are short and self-contained):
- God Nodes — top 5-10 lines
- Surprising Connections — keep edge format with confidence tag
- Suggested Questions — keep the betweenness/INFERRED rationale lines

**Don't paste** (too long, summarize instead):
- Communities — name the top 3-4 communities with their cohesion scores
- Hyperedges — only if there's something striking, like a hyperedge that crosses 3+ community boundaries
- Knowledge Gaps — only mention if isolated_nodes > 30% of total nodes (signals weak extraction)

## Picking the follow-up question

The Suggested Questions section is generated topologically. Two types appear:

1. **Bridge questions** — "Why does X connect Community A to Community B, C, D?" Phrased with `(betweenness centrality 0.NNN)`. **These are the gold** — they ask about real cross-cutting concerns the graph found.
2. **Verification questions** — "Are the N inferred relationships involving X actually correct?" These ask the user to verify model speculation. Useful in deep-mode runs but not as exciting.

**Pick the bridge question with the highest betweenness centrality.** That node connects the most worlds in the graph. Phrase the offer as:

> "The most interesting question this graph can answer: **<question>**. Want me to trace it?"

If the user says yes:
```
/graphify query "<question>"
```

Then walk them through the resulting subgraph: which communities the path crosses, which nodes are bridges, what the path reveals.

## Reading cohesion scores

Each community has a cohesion score (0.0–1.0). Quick guide:

| Score | Meaning |
|---|---|
| > 0.7 | Tight cluster, high internal connectivity. Represents a real concept. |
| 0.4–0.7 | Reasonable cluster. Most communities sit here. |
| < 0.4 | Loose cluster. Often a "miscellaneous" bucket or weak topic. Mention to user as "loose grouping, may not be a real concept." |
| 1.0 with size 2 | Just two strongly-connected nodes. Often a doc + its rationale, or a function + its caller. Not noteworthy. |

## Reading EXTRACTED / INFERRED / AMBIGUOUS ratio

In Summary:
```
Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS
```

| Ratio pattern | Means |
|---|---|
| EXTRACTED > 70% | Healthy. Mostly explicit relationships (imports, citations). |
| EXTRACTED 50-70% + INFERRED 30-50% | Normal for mixed-content corpora. |
| INFERRED > 50% | Either deep mode was on, or extraction was speculative. Warn user that many edges are model guesses. |
| AMBIGUOUS > 0 | Deep mode was on (baseline never produces AMBIGUOUS). Treat AMBIGUOUS edges as "review these specifically." |

## When to flag concerns to the user

Surface these without being asked:

- **>50% isolated nodes**: extraction missed many connections. Recommend `--mode deep` re-run, or check if files have extractable content (PDFs without pypdf will fail silently — see troubleshoot.md).
- **All communities < 5 nodes**: clustering didn't find structure. Either corpus is too small or files are too disconnected. Tell user the graph may not be useful at this size.
- **One giant community + several singletons**: classic Leiden resolution problem. Suggest `--cluster-only` rerun, or note that the corpus may be too homogeneous.
- **God nodes are all docstring/module objects**, not real abstractions: extraction picked structural noise over semantic content. Common with code-only corpora; usually fine, just frame it that way.

## Example follow-up flow

After a run, user sees the three sections. You then say:

> "The most interesting question this graph can answer: **Why does Transformer architecture connect Transformer Foundations to Self-Attention Rationale, Multi-Head & Scaled Attention, and Encoder-Decoder Stack?** Want me to trace it?"

If yes: run `/graphify query "..."`, then narrate the path:
- Which start nodes the question matched
- Which community each hop crosses
- What pattern the bridges reveal
- End with a follow-up offer ("this connects to X — want to go deeper?")

The graph is the map. Your job after the pipeline is to be the guide.
