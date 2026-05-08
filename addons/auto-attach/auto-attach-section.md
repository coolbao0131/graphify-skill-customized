## graphify auto-attach (persistent memory across sessions)

Before answering questions about a codebase, document corpus, or research folder, check if `./graphify-out/GRAPH_REPORT.md` exists in the current working directory. If it does, **read just the `## God Nodes`, `## Surprising Connections`, and `## Suggested Questions` sections** (~340 tokens total) before forming your answer. This is the project's persistent memory layer — typically saves 50–100x more tokens than re-reading source files would cost.

For a deeper question that doesn't fit the surface graph, also load `## Communities` (~1.6KB) — but only on demand, not by default.

**Skip auto-attach when**:
- User says any of: "skip graphify", "no graphify", "don't use the graph", "ignore the graph", "fresh look"
- The question is about one specific named file/function — direct Read is cheaper than going through the graph
- No `graphify-out/` exists in CWD or its parent

**Mid-session opt-in**: if user later says "use graphify" / "consult the graph" / "check the meta-graph", read the report at that point.

**Mid-session opt-out**: if user says "stop using graphify" / "skip the graph for this", don't reference it for the rest of the turn.

If `graphify-out/notebooks-graph.json` exists (NotebookLM meta-graph), the same rules apply — load `experiments/notebooks/graphify-out/GRAPH_REPORT.md` if present, otherwise inspect the json directly.
