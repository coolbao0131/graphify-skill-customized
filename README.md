# graphify-skill (customized)

Customized fork of the [graphifyy](https://github.com/safishamsi/graphify) Claude Code skill.

Started from official `graphifyy v0.4.0` SKILL.md, augmented with:

- **recipes/**: scenario walkthroughs, report-interpretation guide, troubleshooting playbook (loaded on demand, not on every `/graphify` trigger)
- **Workarounds** in SKILL.md for graphifyy package bugs that haven't been upstreamed yet (graphml hyperedge crash, query parser punctuation, `--update` graph_diff direction, etc.)
- **Scenario presets** + **Anti-patterns** sections that weren't in the official skill
- **Known package issues** section tracking what's fixed in upstream vs still needing skill workaround

Tested against `graphifyy v0.6.7` (2026-05-02). For comparison testing data + UT findings see the companion test repo (or local `/Users/tonyhuang/CoolBaoProjects/Graphify/tests/`).

## Layout

```
SKILL.md                         # main, always loaded on /graphify trigger
recipes/
  ├── scenarios.md               # 7 use-case walkthroughs
  ├── interpret-report.md        # how to read GRAPH_REPORT.md
  └── troubleshoot.md            # common failure modes
.graphify_version                # version stamp (matches package + suffix)
```

## Install

Replace your `~/.claude/skills/graphify/` contents with this repo, or `git clone` into it directly.

```bash
cd ~/.claude/skills
mv graphify graphify.bak
git clone https://github.com/coolbao0131/graphify-skill-customized graphify
```

## Sync from upstream

When graphifyy publishes a new version:

```bash
pip install --upgrade graphifyy
# Diff package skill.md against this SKILL.md, port any new Steps,
# verify each existing workaround is still needed against the new code.
```
