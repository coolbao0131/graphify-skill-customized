# Scenario walkthroughs

Detailed playbooks for each scenario in SKILL.md's "Scenario presets" table. Read the section that matches the user's intent.

---

## 1. Onboarding to a new codebase

**Signals from user**: "help me understand this project", "what does this do", "I just joined this team", "I need to add a feature but I'm new here".

**Pipeline**:
```
/graphify . --wiki
```

If the user provided a GitHub URL (`https://github.com/owner/repo`) instead of a local path, SKILL Step 0 automatically calls `graphify clone <url>` first. The repo lands at `~/.graphify/repos/<owner>/<repo>` and that path is what feeds the rest of the pipeline. Subsequent runs reuse the local clone (no re-fetch). For comparing two repos: `graphify clone url1 && graphify clone url2 && /graphify ./url1-path && /graphify ./url2-path && graphify merge-graphs g1.json g2.json`.

**After the run, do this in order:**

1. Surface the **top 5–6 God Nodes** verbatim from the report. Add framing in your own voice: "these are the abstractions to learn first." (The framing is your addition; the report just lists names + degree.)
2. Look at **Communities**. The largest community usually maps to the core domain logic; tiny communities (2-3 nodes) are often utilities or dead code.
3. From Suggested Questions, pick the **bridge question with highest betweenness centrality** (lines containing `_High betweenness centrality (0.NNN)_`). Skip verification questions ("Are the N inferred..."). To pick programmatically:
   ```python
   import re
   text = open('graphify-out/GRAPH_REPORT.md').read()
   bridges = re.findall(r'(\*\*Why does[^*]+\*\*)\s*\n\s*_High betweenness centrality \(([\d.]+)\)', text)
   bridges.sort(key=lambda x: -float(x[1]))
   chosen = bridges[0][0] if bridges else None
   ```
   Offer to trace it via **`/graphify query "<the question>"`** — pass the question text directly. (Don't use `path` here: the question is "Why does X connect A, B, C" — it's 1-to-many, not a 2-endpoint path.)
4. If `--wiki` was used, tell the user: "Open `graphify-out/wiki/index.md` as your reading map. Each community article walks through the concept." If wiki/index.md doesn't exist (rare — to_wiki failure), fall back to GRAPH_REPORT.md only.

**Don't**:
- Don't add `--mode deep` for first-time onboarding. INFERRED edges introduce ~2.5x more speculative connections; before the user knows the codebase, they can't tell signal from noise.
- Don't run `--obsidian` for codebases >150 functions. One note per node is too noisy. Wiki gives one article per community, much more readable.

---

## 2. Personal /raw research vault (Karpathy-style)

**Signals**: "I want to build a knowledge base", "drop everything in", "research vault", "/raw folder", references to long-running corpus.

**Initial setup** (once):
```
/graphify ~/raw --obsidian --obsidian-dir ~/vaults/raw
```

If the user has an existing Obsidian vault, point `--obsidian-dir` at it directly — graphify writes side-by-side files and a `graph.canvas`, doesn't disturb existing notes.

**Adding new items** (per item):
```
/graphify add <url> --contributor "<user-name>"
```

Supported URL types (verified): arxiv abstracts, arxiv PDFs (auto-redirected to abstract), direct PDFs, Twitter/X via oEmbed, plain webpages, YouTube (downloads audio for later transcription), images.

**Batch update** (weekly cadence works well):
```
/graphify ~/raw --update
```

`add` only downloads to `raw/`; the graph doesn't change until `--update` runs. If the user is using `--obsidian-dir <vault>`, **also re-run obsidian export after `--update`** to sync new nodes into the vault — the update step rebuilds graph.json but does NOT touch the vault by default:
```bash
$(cat graphify-out/.graphify_python) -c "
import json
from graphify.build import build_from_json
from graphify.export import to_obsidian, to_canvas
from graphify.cluster import cluster, score_all
from networkx.readwrite import json_graph
data = json.loads(open('graphify-out/graph.json').read())
G = json_graph.node_link_graph(data, edges='links')
communities = cluster(G)
to_obsidian(G, communities, '<vault-path>')
to_canvas(G, communities, '<vault-path>/graph.canvas')
"
```
Warn the user that graphify regenerates note files in the vault — don't edit graphify-managed notes in place; add separate notes alongside.

**Querying** (any time, even weeks later):
```
/graphify query "what's the latest on <topic>?"
/graphify path "<concept A>" "<concept B>"
```

**Cost notes**:
- `--update` does NOT save semantic cost on doc/paper changes (PKG-3 cache bug). Tell the user before they batch big updates: "this will re-run subagents on all changed docs."
- For an active corpus, batching weekly (one update with N new docs) is cheaper than per-doc updates because of subagent dispatch overhead.

---

## 3. Active development on a code project

**Signals**: "keep the graph current", "I'm working on this every day", "team uses this".

**One-time setup**:
```
/graphify .                    # initial graph
graphify hook install          # post-commit + post-checkout AST rebuild
graphify claude install        # CLAUDE.md + .claude/settings.json hook
```

After this:
- Every `git commit` rebuilds the code portion of the graph automatically (AST, no LLM, ~2 seconds for typical commit).
- Other Claude Code sessions see the graph via CLAUDE.md and use it before answering codebase questions.
- Doc/image changes still need a manual `/graphify . --update` (doc rebuild requires LLM).

**Optional**: serve as MCP for other tools:
```
python -m graphify.serve graphify-out/graph.json &        # background, current shell
# OR run in a separate terminal — this is a long-running stdio server, not a one-shot
```
Tell the user it's foreground-blocking by default; they need `&` or a separate terminal/tmux pane.

**Don't**:
- Don't add `python -m graphify.watch` on top of the git hook. They overlap — hook is commit-driven and cleaner.
- Don't run `--update` after every code commit. The hook already handles code; only run `--update` when a doc/paper/image changed.

---

## 4. Paper review / survey writing

**Signals**: "I'm reading 5+ papers this week", "writing a survey", "find connections across these papers", "what do these papers have in common".

**Setup** (gather corpus first):
```bash
mkdir survey-<topic> && cd survey-<topic>
/graphify add https://arxiv.org/abs/...   # for each paper
/graphify add https://arxiv.org/abs/...
# ...
```

**Run with deep mode** (this is one of the few cases where deep mode is worth the token cost):
```
/graphify . --mode deep
```

Deep mode produces ~2.5x more INFERRED edges and adds AMBIGUOUS edges. For survey writing, this is exactly what you want — non-obvious cross-paper connections.

**After the run**:

1. Show **Surprising Connections** section. This is where graphify earns its keep on paper corpora — it surfaces concepts that two papers solve differently or that share unexpected mechanism. If >10 surprising connections, surface the top 5 by `confidence_score` and mention "+ N more in the report."
2. **Always state the confidence label** when narrating a surprising edge — most are INFERRED (model speculation) or AMBIGUOUS (low confidence). The user needs to know which edges are model guesses before treating them as real.
3. For each surprising connection worth exploring, offer **`/graphify query "<phrase based on the edge>"`** rather than `path`. The surprising edges themselves are already 1-hop in the graph — `path` would just echo the edge. `query` returns the surrounding subgraph (related concepts, supporting nodes), which is what the user actually wants for survey writing.
4. **Communities** in paper corpora often map to "schools of thought" — point them out: "Community 0 is mostly the X school, Community 2 is the Y school. The bridges between them are at <node list>."
5. Use `/graphify explain "<concept>"` to get all citations + connections for any single concept the user is writing about.

---

## 5. MCP integration (other agents query the graph)

**Signals**: "let Cursor use this", "expose to Claude Desktop", "connect to my agent", "MCP server".

**Setup**:
```
/graphify .
python -m graphify.serve graphify-out/graph.json
```

The server exposes 7 tools via stdio MCP: `query_graph`, `get_node`, `get_neighbors`, `get_community`, `god_nodes`, `graph_stats`, `shortest_path`.

**Claude Desktop config** (write this snippet for the user):
```json
{
  "mcpServers": {
    "graphify": {
      "command": "python3",
      "args": ["-m", "graphify.serve", "/abs/path/to/graphify-out/graph.json"]
    }
  }
}
```

**Cursor / Claude Code / any MCP client**: same pattern — point at `python -m graphify.serve <abs-path-to-graph.json>`.

**Verify it works**:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' | \
  python -m graphify.serve graph.json
```

Should return a JSON-RPC response with `serverInfo.name == "graphify"`.

---

## 6. Embed the graph elsewhere (Notion / GitHub / Gephi / Neo4j)

**Signals**: "embed in Notion", "put in README", "import to Gephi", "Neo4j".

**One-pass export**:
```
/graphify . --svg --graphml --neo4j
```

This produces:
- `graph.svg` (~250KB typical) — drop into Notion, Obsidian, GitHub README, any markdown renderer
- `graph.graphml` — open in Gephi, yEd, or any GraphML tool. SKILL Step 7c strips list/dict/None attrs that would otherwise crash the writer.
- `cypher.txt` — `cypher-shell < graphify-out/cypher.txt` to import into Neo4j (uses MERGE, safe to re-run)

**Don't**:
- Don't use `--neo4j-push bolt://...` unless the user explicitly has Neo4j running and provided credentials. Cypher file is safer (no live DB modification).
- Don't generate SVG for graphs >2000 nodes. Spring layout takes minutes and produces unreadable output.

---

## 7. Re-cluster cheaply

**Signals**: "the communities don't make sense", "redo the grouping", "I added labels but want fresh communities".

**Cheap rerun**:
```
/graphify . --cluster-only
```

Skips Steps 1-3 entirely. Only re-runs Leiden clustering on the existing `graph.json`. No LLM cost. Useful when:
- You manually edited graph.json and want fresh community assignment
- The previous run's communities looked off (e.g. one giant community swallowed everything — Leiden has resolution sensitivity)
- You want to compare community structure with vs. without certain edges
