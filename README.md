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
Found 6 session(s) in /home/user/projects/endotypes
  codex    2026-09-25  "fix the endotype clustering..."   <- latest work
  claude   2026-09-18  "add the GSE cohort loader..."
  ...

Continue with: codex (its edits match the files on disk; the Claude sessions
were read-only questions)
  Advice: cd /home/user/projects/endotypes && codex

$ mainai --handoff .
...
Wrote /home/user/projects/endotypes/HANDOFF.md
```

1. Reads every agent's stored conversations, keeps the ones for the given
   folder.
2. Decides which agent to continue with. An LLM reads each session's actual
   content (not just the newest timestamp) and recommends one, with its
   reasoning printed alongside the pick.
3. Prints advice: the command to run to continue with that agent. mainai
   never launches anything itself.

The folder argument is required (`mainai .` for the current directory) --
`mainai` with no arguments prints help and does nothing, so a stray bare
invocation after install never spends tokens or bills an API key unasked.

Flags: `--list` (sessions + a free file-evidence guess only, no LLM call, no
file written), `--agent NAME` (override the pick, no LLM call), `--handoff`
(also summarize the other agents' sessions into `HANDOFF.md`, one extra LLM
call), `--handoff-agents grok[,codex,...]` (summarize only the named
agent(s) instead of every agent other than the one picked -- implies
`--handoff`; e.g. continue with Claude via `--agent claude` while still
pulling in context from Grok via `--handoff-agents grok`), `-y`/`--yes`
(skip the confirmation before an LLM call that would bill
`ANTHROPIC_API_KEY` directly, when no claude.ai subscription login is
found).

See `mainai.md` for the full design notes (reader architecture, per-agent log
formats, picker logic, summarizer, scope/build order).

## Status

Readers for Claude Code, Codex, and Grok, the LLM-based picker, `--handoff`,
and the CLI are implemented. Published to PyPI as `mainai`.

## Development

uv-managed project.

```bash
uv sync
uv run mainai --list .
```
