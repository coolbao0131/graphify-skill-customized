## graphify auto-attach (persistent memory across sessions)

Before answering questions about a codebase, document corpus, or research folder, check if `./graphify-out/GRAPH_REPORT.md` exists in the current working directory. If it does, **read just the `## God Nodes`, `## Surprising Connections`, and `## Suggested Questions` sections** (~340 tokens total) before forming your answer. This is the project's persistent memory layer — typically saves 50–100x more tokens than re-reading source files would cost.

For a deeper question that doesn't fit the surface graph, also load `## Communities` (~1.6KB) — but only on demand, not by default.

**Skip auto-attach when**:
- User says any of: "skip graphify", "no graphify", "don't use the graph", "ignore the graph", "fresh look"
- The question is about one specific named file/function — direct Read is cheaper than going through the graph
- The question is about **runtime behavior, performance, or debugging** ("why is X slow", "where does this error come from", "what does X output", "trace why this race happens"). The graph is structural/static — it can't answer behavior. Use Read/Grep on the actual code path instead.
- The question is a **direct action on a known target** ("show me X", "format Y", "add a comment to Z", "rename A to B in C", "what does line 47 do"). Skip the graph; the target is already named.
- No `graphify-out/` exists in CWD or its parent

**Stale-graph awareness (drift-based, not time-based)**: after reading `GRAPH_REPORT.md`, measure how far the graph has drifted from the actual corpus.

For a normal codebase / docs corpus: walk CWD (skip `graphify-out`, `.git`, `node_modules`, `__pycache__`, `.venv`, `dist`, `build`, `.next`, `target`) and find the newest file's mtime. Compare to `./graphify-out/graph.json` mtime:

- newest file ≤ graph.json: **no warning** (graph is current)
- newest file is 0–12h newer than graph.json: **silent** (likely just an edit in progress)
- newest file is 0.5d–7d newer, OR ≤5 files newer: append a **soft caveat** like `_(graph N days behind corpus, e.g. \`auth/session.py\` changed since build — relevant edges may be missing)_`
- newest file is >7d newer, OR >5 files newer: append a **strong caveat** advising `/graphify . --update` BEFORE relying on the graph for this answer

For the NotebookLM meta-graph at `experiments/notebooks/graphify-out/notebooks-graph.json`: drift = max(`updated_at` from `nlm notebook list`) vs the meta-graph's `built_at`. Same severity ladder, but mention `/graphify sync-notebooks --update` instead.

Why drift-based not time-based: a static research corpus untouched for 30d is fine, while an active codebase with 50 commits in the last 12h is dangerously stale at any wall-clock age. Drift measures relevance directly. Cost: one `os.walk` (<0.1s) per session that uses the graph.

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
