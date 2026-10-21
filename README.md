# mainai

A CLI that figures out which coding agent (Claude Code, Codex, Grok,
...)  last did real work in a project folder, and hands off cleanly to
the one you pick next.

## The problem

Working the same project folders with several coding agents means that
coming back weeks or months later, it's unclear which agent did the
most recent real work, and what the other agents did in the meantime.

## What it does

```
$ export ANTHROPIC_API_KEY=sk-ant...
$ pipx install mainai
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
Launching: codex resume --last "Read HANDOFF.md and integrate it into our existing conversation"
```

1. Reads every agent's stored conversations, keeps the ones for the given
   folder.
2. Decides which agent to continue with. An LLM reads each session's actual
   content (not just the newest timestamp) and recommends one, with its
   reasoning printed alongside the pick.
3. Prints advice: the command to run to continue with that agent.
4. With `--handoff`, also summarizes the other sessions into `HANDOFF.md`
   and launches the picked agent itself, continuing its most recent
   conversation and feeding it a prompt to read `HANDOFF.md`.

The folder argument is required (`mainai .` for the current directory) --
`mainai` with no arguments prints help 

Uses Claude LLM, hence requires ANTHROPIC_API_KEY

Flags: `--list` (sessions + a free file-evidence guess only, no LLM call, no
file written), `--agent NAME` (override the pick, no LLM call), `--handoff`
(summarize the other agents' sessions into `HANDOFF.md`, one extra LLM
call, then launch the picked agent -- continuing its most recent
conversation and pointing it at `HANDOFF.md`; **Linux/macOS only**),
`--handoff-agents grok[,codex,...]` (summarize only the named agent(s)
instead of every agent other than the one picked -- implies `--handoff`,
but never launches anything, even combined with `--handoff`; e.g. continue
with Claude via `--agent claude` while still pulling in context from Grok
via `--handoff-agents grok`), `-y`/`--yes` (skip the confirmation before an
LLM call that would bill `ANTHROPIC_API_KEY` directly, when no claude.ai
subscription login is found).

## Platform support

Developed and tested on Linux and macOS only; Windows is untested.

See `mainai.md` for the full design notes (reader architecture, per-agent log
formats, picker logic, summarizer, scope/build order).

## Status

Supports Claude Code, Codex, and Grok

