# graphify auto-attach (CLAUDE.md patch)

Optional addon that teaches Claude Code **how to use graphify intelligently across sessions** — not just "always on" or "always off", but a context-aware rule set that decides per-question.

## What it does

Adds a section to your global `~/.claude/CLAUDE.md` (or any project-level `CLAUDE.md`) that instructs Claude to:

- **Auto-read** `GRAPH_REPORT.md`'s God Nodes / Surprising Connections / Suggested Questions sections (~340 tokens) at the start of architectural / cross-cutting questions — when `graphify-out/` is present **and** the question warrants it
- **Skip the graph** when:
  - User says "skip graphify" / "no graphify" / "ignore the graph"
  - The question is about ONE specific named file/function (direct Read is cheaper)
  - The question is about runtime behavior / performance / debugging (graph is static, can't answer)
  - The question is a direct action on a known target ("show me X", "format Y", "rename A to B")
- **Offer to build** (once per session) when no graph exists yet AND the question is architectural AND the directory is big enough (>20 files) AND it's not a scratch/throwaway dir
- **Warn about staleness** — drift-based check: walk the corpus and compare newest file mtime vs `graph.json` mtime. Soft caveat for moderate drift (5+ files newer or 0.5–7 days), strong caveat advising `--update` for severe drift (>5 files OR >7 days)
- **Mid-session toggle** via natural language: "use graphify" / "stop using graphify"

The injected text is in [`auto-attach-section.md`](./auto-attach-section.md) — read it before installing.

## Token cost / benefit

Per session, regardless of directory:

| | Tokens loaded |
|---|---|
| Rule itself in CLAUDE.md (always loaded at session start) | **~1150** |
| Plus per session that uses the graph: GRAPH_REPORT god/surprising/suggested sections | +~340 |
| Plus per session needing drift check: one `os.walk` | <0.1s, negligible tokens |

That's higher than the early v1 (~354 tokens) — the cost grew because we layered conditional logic for the four scenarios above.

**Break-even math**: the rule pays for itself when it prevents Claude from re-Reading source files for ONE architectural question. A 50KB codebase Read is ~12,500 tokens, so 1150-token rule saves 11x on the first hit.

If you only ever do small file-specific tasks (the rule is "wasted" most of the time), `~1150` tokens/session is the cost of having the rule available when needed. To skip entirely: `./uninstall.sh`.

## Install

```bash
cd addons/auto-attach
./install.sh                            # global: patches ~/.claude/CLAUDE.md
TARGET=./CLAUDE.md ./install.sh         # project-level: patches CLAUDE.md in cwd
./install.sh --dry-run                  # preview without writing
```

The script:
1. Backs up the target with timestamp suffix (`.bak.YYYYMMDD-HHMMSS`)
2. Auto-prunes backups older than the most recent 5 (so they don't accumulate forever)
3. Appends the section wrapped in `BEGIN/END` HTML-comment markers
4. **Idempotent** — running twice is a no-op (use uninstall first if you want to refresh content)

## Uninstall

```bash
./uninstall.sh                          # remove from ~/.claude/CLAUDE.md
TARGET=./CLAUDE.md ./uninstall.sh       # remove from project CLAUDE.md
```

Removes everything between BEGIN/END markers, collapses whitespace. Backups preserved.

## Verifying it works

After install, open a **new** Claude Code session (existing ones don't pick up CLAUDE.md changes mid-flight) in a dir with `graphify-out/GRAPH_REPORT.md`. Try these:

| Question type | Expected behavior |
|---|---|
| "What are the core modules?" (architectural) | First tool call: `Read graphify-out/GRAPH_REPORT.md` |
| "Show me cli.py" (direct action) | Skips graph, goes straight to `Read cli.py` |
| "Why is this slow?" (behavioral) | Skips graph, uses Grep/Read on actual code path |
| Same Q after `touch` on a file | Should append a soft drift caveat: `_(graph N days behind corpus, e.g. \`X\` changed since build)_` |

If Claude doesn't behave this way, re-run `./install.sh` and start a fresh session.

## Project-level vs global

- **Global** (`~/.claude/CLAUDE.md`): rule applies in every Claude Code session anywhere
- **Project-level** (`<project>/CLAUDE.md`): rule applies only when CWD is in that project

Both can coexist — project CLAUDE.md is loaded *in addition to* global, not instead. The rule itself is a no-op when no `graphify-out/` is present.

## Disabling without uninstalling

| Scope | How |
|---|---|
| This question | Ask about a specific file ("show me X") — rule auto-skips |
| This session | Say "skip graphify" / "no graphify" / "fresh look" |
| Permanently | Run `./uninstall.sh` |

## Why this beats `graphify claude install`

The official `graphify claude install` command also patches CLAUDE.md and adds a `.claude/settings.json` PreToolUse hook. That one is **always-on, hooks every tool call** — no easy mid-session opt-out, no behavioral/direct skip awareness, no drift detection.

This addon is more nuanced:

| | `graphify claude install` (official) | This addon |
|---|---|---|
| When graph used | Always (PreToolUse hook fires) | Conditional (architectural Q only) |
| File-specific Q | Still consults graph | Skips |
| Behavioral / debug Q | Still consults graph | Skips |
| Stale graph | No warning | Drift check + caveat |
| No-graph dir | No suggestion | Offers to build (once) |
| Toggle | Re-uninstall hook | Natural language |
| settings.json | Modified | Untouched |
| Token cost / session | ~200 (just hook config) | ~1150 (rule logic) |

If you want the heavyweight always-on behavior for a particular project, run `graphify claude install` *in that project*. They coexist fine — global=this addon, project=official hook.

## Files

```
addons/auto-attach/
├── auto-attach-section.md   ← canonical text injected (read this for exact rule)
├── install.sh               ← idempotent installer + backup rotation
├── uninstall.sh             ← removes between markers
└── README.md                ← this file
```
