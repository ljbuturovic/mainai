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
Run: cd /home/user/projects/endotypes && codex resume --last "Read HANDOFF.md and integrate it into our existing conversation"
```

1. Reads every agent's stored conversations, keeps the ones for the given
   folder.
2. Decides which agent to continue with. An LLM reads each session's actual
   content (not just the newest timestamp) and recommends one, with its
   reasoning printed alongside the pick.
3. Prints advice: the command to run to continue with that agent.
4. With `--handoff`, also summarizes the other sessions into `HANDOFF.md`
   and prints the command to continue the picked agent's own conversation,
   pointed at `HANDOFF.md`. mainai never runs it for you.

The folder argument is required (`mainai .` for the current directory) --
`mainai` with no arguments prints help 

Uses Claude LLM, hence requires ANTHROPIC_API_KEY

## Flags

```
$ mainai
usage: mainai [-h] [--list] [--agent NAME] [--handoff] [--handoff-agents AGENT[,AGENT...]] [-y] [--version] folder

Find which coding agent (Claude Code, Codex, ...) last did real work in a project folder, and show which one to continue with.

positional arguments:
  folder                project folder to inspect, e.g. `.` for the current directory

options:
  -h, --help            show this help message and exit
  --list                show the sessions found and a quick file-evidence guess, nothing else (no file written, no LLM call)
  --agent NAME          override the pick, e.g. --agent codex (no LLM call)
  --handoff             summarize the other agents' sessions into HANDOFF.md (uses an LLM), then print the command to continue the picked agent's conversation, pointed at HANDOFF.md. mainai never runs it for you.
  --handoff-agents AGENT[,AGENT...]
                        with --handoff, summarize only these agents' sessions into HANDOFF.md instead of every agent other than the one picked (comma-separated, e.g. --handoff-agents grok). Implies --handoff, but does NOT print a continue command -- useful to continue with one agent
                        (--agent) while still pulling in context from a specific other one.
  -y, --yes             don't ask for confirmation before an LLM call that would bill ANTHROPIC_API_KEY directly (no claude.ai subscription login found)
  --version             show program's version number and exit
```

## Platform support

Developed and tested on Linux and macOS only; Windows is untested.

See `mainai.md` for the full design notes (reader architecture, per-agent log
formats, picker logic, summarizer, scope/build order).

## Status

Supports Claude Code, Codex, and Grok

