# MainAI (mainai) - project brief

Handoff notes from a Claude Code session in ~/Dropbox/ai/ai (2026-10-04/05).
Nothing has been built yet; this file is the starting point.

## The problem

LB works in the same folders with several coding agents (Claude Code, Codex,
Grok, maybe Gemini later). Coming back to a project months later, it is
unclear which agent did the most recent real work, and what the other agents
did in the meantime.

## What mainai does

One CLI command, run on a project folder:

1. Read every agent's stored conversations, keep the ones for that folder.
2. Decide which agent to continue with.
3. Summarize the relevant parts of the *other* agents' sessions into
   HANDOFF.md.
4. Start the chosen agent, already pointed at HANDOFF.md.

## User interaction (decided)

A single command. Remembering two commands was called a showstopper.

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

- `mainai` with no arguments prints help and does nothing. The folder
  argument (`.`) is the "go" signal, so a stray bare `mainai` never spends
  LLM usage.
- Optional flags:
  - `--list`: show sessions and the pick only; no LLM call, writes nothing
  - `--agent NAME`: override the pick
  - `--no-launch`: write HANDOFF.md but do not start the agent
- Launching works because `claude`, `codex` and `grok` all accept a starting
  prompt on the command line.

## Design

1. **One reader per agent.** Each converts its own log format into a common
   record: agent, session id, folder (cwd), start/end time, turns (role,
   text), files touched, commands run. A new agent = one new reader.
2. **Filter by folder.** Match the session's cwd to the target folder or a
   subfolder.
3. **Pick the agent.** Raw "latest message" can mislead (a trivial side
   question can be the newest message). The stronger signal is file evidence:
   compare the files each session wrote with what is on disk now. The session
   whose edits match the current files did the latest real work. Use git
   history too when the folder is a repo. Print the pick and the reasons.
4. **Summarize the others.** First extract without an LLM (user prompts, final
   assistant answers, files changed, decisions, errors), then have an LLM
   condense that into HANDOFF.md with sections: goal, done, decisions + why,
   open items, gotchas, key files. Tag each item with agent and date.
5. **Hand off.** Launch the chosen agent with a prompt to read HANDOFF.md.

## Summarizer: `claude -p` (recommended)

Claude Code's headless mode: give it a prompt, it prints the answer and exits.
It uses the existing Claude login and plan (no API key, no extra
dependencies). The planned call (flags exist in Claude Code 2.1.289; verify
the exact combination when building):

```
claude -p "<summarize instructions>" --model sonnet --output-format json \
       --no-session-persistence --tools ""
```

- `--no-session-persistence` is essential: without it, each summarizing run
  saves its own transcript into ~/.claude/projects, and mainai would then
  read and summarize its own runs.
- `--tools ""` (or a minimal list): the summarizer only needs the text given.
- Keep the summarizer behind a small interface so the Anthropic API,
  `codex exec` or `grok -p` can be swapped in with a flag.
- Privacy: the transcripts (including Codex/Grok ones) go to Anthropic.

The API alternative needs a key, bills per token separately and adds a
dependency, but gives full control (caching, batching). Not worth it for a
personal tool.

## Where each agent stores sessions (verified on disk)

Locations differ per machine. Two machines so far:

| Agent | beograd (laptop) | ljubljana |
|---|---|---|
| Claude Code | ~/.claude/projects/<path-slug>/<session>.jsonl | same |
| Codex | ~/snap/codex/<rev>/sessions/YYYY/MM/DD/rollout-*.jsonl (snap; check data survives snap refreshes) | ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl (48 files, 2025-09 to 2026-09) |
| Grok | not installed | ~/.grok/sessions/<url-encoded cwd>/<session-id>/ (grok 1.0.44) |
| Gemini | not installed | not installed |

Format notes:

- **Claude Code**: JSONL, one event per line. `cwd`, `timestamp`,
  `sessionId`, `gitBranch` on each user/assistant line. Path slug = cwd with
  `/` replaced by `-`. Also a `sessions-index.json` per project dir.
- **Codex**: JSONL. First line `type: session_meta` with `payload.cwd`,
  `payload.id`, `payload.timestamp`. Then `response_item` (message,
  function_call, function_call_output, reasoning), `event_msg` (user_message,
  agent_message, token_count), `turn_context`. Also ~/.codex/history.jsonl
  and ~/.codex/session_index.jsonl on ljubljana.
- **Grok**: the folder name is the URL-encoded cwd (e.g.
  `%2Fhome%2Fljubomir%2FDropbox%2Fai%2Fcvic`), which makes folder filtering
  easy. Per session: `chat_history.jsonl` (messages; first line is the system
  prompt), `events.jsonl` (ts, type, session_id, model_id), `summary.json`,
  `rewind_points.jsonl`, `updates.jsonl`. Per folder: `prompt_history.jsonl`.
  Also ~/.grok/sessions/session_search.sqlite. Not parsed in detail yet.

All formats are undocumented and change between versions; readers must be
tolerant (skip unknown line types, never crash on one bad line).

## Retention: Claude Code deletes old transcripts

Claude Code deletes transcripts after 30 days by default
(`cleanupPeriodDays`). On beograd only 5 transcripts were left (oldest
2026-09-15). So for 6-month-old work, Claude's side may simply be gone.

- beograd: `"cleanupPeriodDays": 36500` set in ~/.claude/settings.json on
  2026-10-04.
- ljubljana: set on 2026-10-05 (9 transcripts left, oldest 2026-09-04).

mainai should warn when a folder has no or few Claude sessions and the
setting is at its default.

## Scope

- v1: Claude Code + Codex readers. Grok reader next (its data is on
  ljubljana). Gemini when installed.
- Build order: readers + session listing (`mainai . --list`) first, no LLM,
  to check it finds the right sessions; then the picker; then the summarizer
  and launch.

## GitHub release (discussed, not decided)

Plausibly worth releasing: multi-agent users are a growing group, and
cross-agent handoff is the distinguishing feature; per-agent readers invite
contributions. The cost is maintenance: undocumented log formats break
readers on agent upgrades. Plan: use it personally for a few weeks first,
search GitHub for prior art, then decide (or publish "as-is").

## Conventions

- Python, uv-managed venv (no system pip installs). Executable entry point
  with a shebang and argparse help that shows option defaults.
- Never write `__pycache__` (check the global CLAUDE.md on the machine in
  use; the shebang convention differs between beograd and ljubljana).
- Markdown/text files plain ASCII (LB edits in Emacs).
