# Troubleshooting

When something fails or looks wrong. Match the symptom, run the diagnostic, apply the fix.

---

## Symptom: "ERROR: Graph is empty - extraction produced no nodes"

Step 4 printed this and stopped. Possible causes:

1. **All files were skipped**. Check Step 2 detect output — if `total_files: 0`, the path was wrong or has no supported extensions.
2. **PDF / docx / xlsx silently empty**. PKG-1: ImportError on pypdf/python-docx/openpyxl is swallowed. Run:
   ```bash
   $(cat graphify-out/.graphify_python) -c "from graphify.detect import extract_pdf_text; from pathlib import Path; print(len(extract_pdf_text(Path('<one-pdf>'))))"
   ```
   If 0, run Step 1 again to install extras (`pip install pypdf html2text python-docx openpyxl`).
3. **Subagents all failed**. Check `.subagent_chunkN.json` files — if missing or contain `null`, all subagents returned invalid JSON. Re-dispatch Step 3 Part B.
4. **AST extraction returned 0** on code-only corpus. Means files are not in supported language extensions. Check `graphify.extract.LanguageConfig` for the list.

---

## Symptom: Communities don't make sense (one giant + many singletons)

Leiden resolution sensitivity. Quick fix:

```
/graphify . --cluster-only
```

Re-runs clustering only (no LLM cost). Leiden has stochastic initialization, so the result may differ. If it still looks bad after 2-3 cluster-only runs, the corpus probably is genuinely homogeneous.

If you want to inspect graph_diff between cluster runs:
```python
# in graphify-out/
import json, networkx as nx
from networkx.readwrite import json_graph
data = json.loads(open('graph.json').read())
G = json_graph.node_link_graph(data, edges='links')
# G.graph might have 'communities' attr, otherwise check node attrs
```

---

## Symptom: God nodes are all docstring/module-level garbage

Like "Module docstring..." or "import statements" appearing as god nodes. Extraction picked up structural noise. Two cases:

1. **Code-only corpus, AST is doing module-as-node**. Normal. Frame to user as "these are the file modules; the abstractions inside them are the next level down."
2. **Doc corpus with long YAML frontmatter or markdown headers**. The first heading or frontmatter block became a node. Subagent prompt could be tightened, but for now treat as noise and pick the next non-trivial god node.

---

## Symptom: Many edges cluster at exactly 0.55 / 0.65 / 0.75 / 0.85 / 0.95

Not a bug. v0.6.6+ uses a discrete confidence rubric for INFERRED edges (rather than continuous 0.6–0.9). Edges should snap to one of those five values. If you see lots of 0.5 specifically, that's a v0.4.0–0.6.5 artifact and means the user is on an outdated graphifyy. Tell them to `pip install --upgrade graphifyy`.

If subagent edges have wildly off scores (e.g. all 0.5 or all 1.0), one specific chunk was lazy. Check `.graphify_semantic.json` source_files and re-dispatch that chunk only.

---

## Symptom: `--update` re-extracts even unchanged files

For doc/paper/image: this is correct behaviour for content-changed files (v0.6.2+ uses content hash, not just mtime, to avoid spurious re-extraction from sync tools).

If unchanged files re-extract anyway, check that the manifest `graphify-out/manifest.json` survived between runs. v0.6.2 fixed a bug where the manifest wasn't persisted, causing every run to re-extract everything. If the user is on <0.6.2, upgrade.

---

## Symptom: `python -m graphify.watch` shows no output

Stdout buffering. Re-run with `-u`:

```bash
python -u -m graphify.watch <path> --debounce 2
```

The watch loop _is_ running silently — the print statements are buffered until newline + flush. With `-u` they appear immediately.

---

## Symptom: Extraction quality is poor (few edges, weak communities) on a corpus you expect to be rich

Likely causes in order of probability:

1. **PDFs aren't being read** (PKG-1). Verify with `extract_pdf_text` test as in "Graph is empty" symptom.
2. **Subagent context limit hit**. If you packed >25 files into one chunk, the subagent may have skimmed. Reduce chunk size to 15-20 and re-run.
3. **Files are formatted in ways the model can't parse** (mostly equations, tables, code blocks with no prose). Subagent extracts named entities and citations; pure-equation papers extract poorly.
4. **Corpus is genuinely small**. Below ~3000 words, the graph is mostly noise. Show user the corpus warning from Step 2 and recommend either adding more material or using direct file read instead of graphify.

---

## Symptom: graph.json is huge (>50MB) and HTML viz is unusable

Corpus exceeded HTML viz threshold. Run with:

```
/graphify . --no-viz --obsidian
```

Skip HTML, use Obsidian's native graph view (handles 5000+ nodes well) or `--wiki` for human reading. Or `--graphml` and load in Gephi for serious analysis.

---

## Symptom: `cost.json` shows input/output tokens = 0 even after expensive runs

SKILL-2: subagents can't self-measure their own token usage in the JSON they output. The cost field is decorative until the harness measures externally. Tell the user the actual token cost is in the Claude Code session summary, not in cost.json.

---

## Symptom: ingest with `--author "Name"` doesn't show author in frontmatter

PKG-6: `--author` only acts as fallback for missing `--contributor` in webpages/arxiv. The frontmatter writes `contributor:`, never `author:`. If user wants both fields:

- For webpages/arxiv, only `contributor` field exists. Tell user.
- For tweets, `author:` is auto-set from oEmbed (the tweet author), `--author` is ignored.

No skill-level fix; this is a graphify package issue.
