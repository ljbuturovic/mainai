# mainai

A CLI that figures out which coding agent (Claude Code, Codex, Grok, ...)
last did real work in a project folder, and hands off cleanly to the one you
pick next.

## The problem

Working the same project folders with several coding agents means that
coming back months later, it's unclear which agent did the most recent real
work, and what the other agents did in the meantime.

## What it does

```
$ mainai .
Found 6 sessions in ~/Dropbox/inflammatix/projects/endotypes
  codex   2026-09-25  "fix the endotype clustering..."   <- latest work
  claude  2026-09-18  "add the GSE cohort loader..."
  ...
Continue with: Codex (its edits match the current files)
Wrote HANDOFF.md (summaries of the 4 Claude sessions)
Launching: codex "Read HANDOFF.md, then continue where we left off."
```

1. Reads every agent's stored conversations, keeps the ones for the current
   folder.
2. Decides which agent to continue with, based on which session's edits
   match the files actually on disk (not just the newest timestamp).
3. Summarizes the relevant parts of the *other* agents' sessions into
   `HANDOFF.md`.
4. Starts the chosen agent, pointed at `HANDOFF.md`.

`mainai` with no arguments prints help and does nothing, so a stray bare
invocation never spends LLM usage. Flags: `--list` (sessions + pick only, no
LLM, no write), `--agent NAME` (override the pick), `--no-launch` (write
`HANDOFF.md` but don't start the agent).

See `mainai.md` for the full design notes (reader architecture, per-agent log
formats, picker logic, summarizer, scope/build order).

## Status

Not yet built. Design only.

## Development

uv-managed project.

```bash
uv sync
uv run mainai --list .
```
