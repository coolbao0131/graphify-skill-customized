# graphify auto-attach (CLAUDE.md patch)

Optional addon that makes Claude Code **automatically consult the graphify graph as persistent memory** when working in any directory that has a `graphify-out/` folder.

## What it does

Adds a section to your global `~/.claude/CLAUDE.md` (or any project-level `CLAUDE.md` you point it at) that instructs Claude to:

- **Auto-read** `GRAPH_REPORT.md`'s God Nodes / Surprising Connections / Suggested Questions sections (~340 tokens) at the start of any architecture / corpus question — when `graphify-out/` is present
- **Skip** when user says "skip graphify" / "no graphify" / "ignore the graph"
- **Mid-session toggle** via natural language ("use graphify" / "stop using graphify")

The section text is in [`auto-attach-section.md`](./auto-attach-section.md) — read it before installing if you want to know exactly what gets injected.

## Token cost / benefit

Per session in any directory:

| Scenario | Tokens added |
|---|---|
| No graphify in CWD | +354 (rule itself, in CLAUDE.md) |
| graphify-out/ exists | +354 + ~340 (auto-loaded sections) ≈ 700 |
| User says "skip graphify" | +354 |

vs. an architecture question that would otherwise re-Read source files (e.g. 50KB code = ~12,500 tokens) → **18–35× win** even on the first hit, much higher across multi-turn sessions.

## Install

```bash
cd addons/auto-attach
./install.sh                            # global: patches ~/.claude/CLAUDE.md
TARGET=./CLAUDE.md ./install.sh         # project-level: patches CLAUDE.md in cwd
./install.sh --dry-run                  # preview without writing
```

The script:
1. Backs up the target with timestamp suffix
2. Appends the section wrapped in `BEGIN/END` HTML-comment markers (so uninstall is clean)
3. **Idempotent** — running twice is a no-op (use uninstall first if you want to refresh)

## Uninstall

```bash
./uninstall.sh                          # remove from ~/.claude/CLAUDE.md
TARGET=./CLAUDE.md ./uninstall.sh       # remove from project CLAUDE.md
```

Removes everything between the BEGIN/END markers + collapses surrounding whitespace. Logs are preserved as `*.bak.<timestamp>`.

## Verifying it works

After install, open a new Claude Code session and `cd` into any directory that has a `graphify-out/GRAPH_REPORT.md`. Ask an architectural question like "what are the core modules?" — Claude should reference god nodes / communities from the graph rather than reading source files one by one.

To confirm Claude is reading the graph:
- Ask "did you check GRAPH_REPORT.md?" — it should say yes
- Or check Claude's tool calls — you should see one `Read` of `graphify-out/GRAPH_REPORT.md` early in the turn

## Disabling without uninstalling

Three ways:

1. **This session only**: say "skip graphify" or "no graph this time"
2. **This question only**: ask about a specific file/function (the rule says skip when question is local, not architectural)
3. **Permanent**: run `./uninstall.sh`

## Project-level vs global

- **Global** (`~/.claude/CLAUDE.md`): the rule applies in every Claude Code session you start, anywhere
- **Project-level** (`<project>/CLAUDE.md`): the rule only applies when working in that project. Use this if you have one project that benefits from auto-attach but don't want it everywhere.

You can have both — project CLAUDE.md is loaded *in addition to* global, not instead.

## Why this beats `graphify claude install`

The official `graphify claude install` command also patches CLAUDE.md and adds a `.claude/settings.json` PreToolUse hook. That one is **always-on for the project** — no easy mid-session opt-out.

This addon is more flexible:
- Toggle by natural language without touching files
- Section is wrapped in markers for clean uninstall
- Doesn't touch `.claude/settings.json` (no hook wiring)
- Skips automatically for file-specific questions

If you want the hard always-on behavior for a particular project, run `graphify claude install` *in that project*. The two patterns coexist fine.
