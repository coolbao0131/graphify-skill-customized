## graphify auto-attach (persistent memory across sessions)

Before answering questions about a codebase, document corpus, or research folder, check if `./graphify-out/GRAPH_REPORT.md` exists in the current working directory. If it does, **read just the `## God Nodes`, `## Surprising Connections`, and `## Suggested Questions` sections** (~340 tokens total) before forming your answer. This is the project's persistent memory layer — typically saves 50–100x more tokens than re-reading source files would cost.

For a deeper question that doesn't fit the surface graph, also load `## Communities` (~1.6KB) — but only on demand, not by default.

**Skip auto-attach when**:
- User says any of: "skip graphify", "no graphify", "don't use the graph", "ignore the graph", "fresh look"
- The question is about one specific named file/function — direct Read is cheaper than going through the graph
- The question is about **runtime behavior, performance, or debugging** ("why is X slow", "where does this error come from", "what does X output", "trace why this race happens"). The graph is structural/static — it can't answer behavior. Use Read/Grep on the actual code path instead.
- The question is a **direct action on a known target** ("show me X", "format Y", "add a comment to Z", "rename A to B in C", "what does line 47 do"). Skip the graph; the target is already named.
- No `graphify-out/` exists in CWD or its parent

**Stale-graph awareness**: after reading `GRAPH_REPORT.md`, check the mtime of `./graphify-out/graph.json` (`stat -f %m` on macOS, `stat -c %Y` on Linux, or in Python `Path('graphify-out/graph.json').stat().st_mtime`). If older than 7 days, append a one-line caveat to your answer: `_(graph last updated N days ago — recent changes may not be reflected; run `/graphify . --update` to refresh)_`. Critical for actively-developed code; research corpora that update monthly are fine.

**Mid-session opt-in**: if user later says "use graphify" / "consult the graph" / "check the meta-graph", read the report at that point.

**Mid-session opt-out**: if user says "stop using graphify" / "skip the graph for this", don't reference it for the rest of the turn.

**Build offer (when no graph exists yet)**: when the user asks an architectural / cross-cutting question — "what does this project do", "how do these modules relate", "find all places X is used", "what changes if I refactor Y", "which files own concept Z" — AND the directory has more than ~20 files AND no `graphify-out/` exists in CWD or its parent, offer ONCE per session:

> "This question is cross-cutting and the directory is big enough that a graph would help. Want me to run `/graphify .` first (~30k input + ~10k output tokens, a few minutes to build; future architectural questions get ~10x token reduction and persist across sessions)? Or I'll grep through this time."

Then wait for the answer. If yes → run `/graphify .` and use the resulting graph. If no → fall back to direct Read/Grep, do not repeat the offer this session.

**Skip the build offer when**:
- Question is about one specific named file/function/line (no graph payoff)
- Directory has <20 files (build cost won't pay back even on first hit)
- Path looks throwaway: `/tmp/`, `*scratch*`, `~/Downloads/`, freshly-created repo with one file
- User already declined or accepted this session
- User is mid-task editing one file (the offer would interrupt flow)

If `graphify-out/notebooks-graph.json` exists (NotebookLM meta-graph), the same rules apply — load `experiments/notebooks/graphify-out/GRAPH_REPORT.md` if present, otherwise inspect the json directly.
