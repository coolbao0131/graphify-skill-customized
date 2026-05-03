# Scheduled meta-graph sync (macOS launchd)

Auto-runs `cli.py sync --update --refresh-summaries` weekly so the meta-graph stays fresh as you add sources to your NotebookLM notebooks. Default: every Sunday 03:00 local time.

**macOS only.** Linux users: adapt to `systemd-timer` or `cron`. Windows: use Task Scheduler.

## Why local, not remote

This job needs:
- NotebookLM auth cookies (stored in `~/.nlm/`)
- Local filesystem access to write `graphify-out/notebooks-graph.json`
- The `notebooklm_tools` Python venv

None of which exist in Anthropic's cloud. So we use macOS `launchd` (the native cron replacement) — runs at the scheduled time, defers gracefully if the laptop is asleep, picks up on next wake.

## Install

```bash
cd experiments/notebooks/scheduled-sync
./install.sh                          # default: Sunday 03:00 local
WEEKDAY=3 HOUR=2 ./install.sh         # override: Wednesday 02:00
```

`install.sh` will:
1. Auto-detect the `notebooklm_tools` Python (via `nlm` on PATH or `~/.local/share/uv/tools/notebooklm-mcp-cli/`)
2. Generate a wrapper script at `experiments/notebooks/.weekly-sync.sh`
3. Render the plist template into `~/Library/LaunchAgents/com.<user>.graphify-notebooks-sync.plist`
4. Bootstrap the job into your user's launchd domain
5. Print test/status/uninstall commands

## Configure

Environment vars `install.sh` reads:

| Var | Default | Meaning |
|---|---|---|
| `WEEKDAY` | `0` (Sun) | 0=Sun, 1=Mon, ..., 6=Sat |
| `HOUR` | `3` | local hour 0–23 |
| `MINUTE` | `0` | local minute 0–59 |
| `LABEL` | `com.<user>.graphify-notebooks-sync` | launchd label (must be unique) |

## Operations

```bash
# Trigger manually right now (for test) — runs the same ~6.5 min sync
launchctl kickstart gui/$UID/com.<user>.graphify-notebooks-sync

# Show next fire time + state
launchctl print gui/$UID/com.<user>.graphify-notebooks-sync | head -30

# Pause without removing
launchctl disable gui/$UID/com.<user>.graphify-notebooks-sync
launchctl enable  gui/$UID/com.<user>.graphify-notebooks-sync

# Full uninstall (keeps logs)
./uninstall.sh
```

## Logs

| File | Content |
|---|---|
| `~/Library/Logs/graphify-notebooks-sync.log` | Each run's `sync --update --refresh-summaries` output, appended with timestamp |
| `~/Library/Logs/graphify-notebooks-sync.stdout.log` | Raw stdout (rarely used; runner already redirects to the .log above) |
| `~/Library/Logs/graphify-notebooks-sync.stderr.log` | launchd's own errors (e.g. plist parse failures) |

Tail the recent run:
```bash
tail -f ~/Library/Logs/graphify-notebooks-sync.log
```

## Cost / impact

- **Wall time per run**: ~6.5 min for 22 notebooks (5 chunks × ~70s + retries)
- **NotebookLM API**: 22 × `cross_notebook_query` summaries — well below typical free-tier rate limit at weekly cadence
- **CPU/network**: trivial; mostly waiting on NotebookLM
- **Battery**: negligible (mostly I/O wait)

## Troubleshooting

| Symptom | Fix |
|---|---|
| `launchctl bootstrap: Bootstrap failed: 5: Input/output error` | A plist with the same Label is already loaded. Run `./uninstall.sh` first. |
| Job never fires | Check macOS System Settings → Login Items & Background Tasks; the agent must be allowed. Also `launchctl print gui/$UID/<label>` should show `state = waiting`. |
| Logs show `Error: Authentication failed` | NotebookLM cookies expired. Run `nlm login` interactively to refresh. |
| Runs stack up after laptop wake | launchd coalesces missed firings into a single run on wake — normal. |

## Why every Sunday?

- Off-peak (less likely to compete with foreground work)
- Aligns with weekly review/planning rhythm
- 7-day cadence matches NotebookLM source ingest patterns most users have

Change to bi-weekly: hard to do in launchd directly. Easiest: set `Weekday` only, then in the runner add `[ $(($(date +%V) % 2)) -eq 0 ] || exit 0` to skip odd weeks.
