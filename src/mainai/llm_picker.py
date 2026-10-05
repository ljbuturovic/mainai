"""LLM-based picker: this is mainai's default decision maker.

Instead of only the file-evidence heuristic in `picker.py`, this asks an LLM
to actually read each session's content -- the summary/title, a capped
excerpt of turns, the files it touched that still exist on disk, and the
commands it ran -- and recommend which agent to continue with, in its own
words. Falls back to `picker.heuristic_pick` when the LLM call fails (CLI
missing, timeout, bad output) or there's only one session to begin with.
"""

from __future__ import annotations

import json
from pathlib import Path

from mainai import llm
from mainai.models import Session
from mainai.picker import Pick, heuristic_pick

MAX_TURN_CHARS = 400
MAX_TURNS_PER_SESSION = 6


def llm_pick(sessions: list[Session], folder: Path) -> Pick:
    if not sessions:
        return Pick(session=None, reasons=["no sessions found for this folder"])
    if len(sessions) == 1:
        return Pick(session=sessions[0], reasons=["only one session found"])

    try:
        raw = llm.call(_build_prompt(sessions, folder))
        data = json.loads(raw)
        agent = data["agent"]
        reason = str(data.get("reason", "")).strip()
    except (llm.LLMError, json.JSONDecodeError, KeyError, TypeError) as exc:
        fallback = heuristic_pick(sessions, folder)
        fallback.reasons.insert(
            0, f"LLM pick unavailable ({exc}); used file-evidence heuristic instead"
        )
        return fallback

    matches = [s for s in sessions if s.agent == agent]
    if not matches:
        fallback = heuristic_pick(sessions, folder)
        fallback.reasons.insert(
            0,
            f"LLM named unrecognized agent '{agent}'; used file-evidence heuristic instead",
        )
        return fallback

    chosen = max(matches, key=lambda s: s.end)
    return Pick(session=chosen, reasons=[reason] if reason else ["LLM pick"])


def _session_excerpt(session: Session) -> dict:
    existing_files = sorted(f for f in session.files_touched if Path(f).exists())
    turns = [
        f"{turn.role}: {turn.text[:MAX_TURN_CHARS]}"
        for turn in session.turns[:MAX_TURNS_PER_SESSION]
        if turn.text.strip()
    ]
    return {
        "agent": session.agent,
        "start": session.start.isoformat(),
        "end": session.end.isoformat(),
        "title": session.title,
        "files_touched_still_on_disk": existing_files,
        "commands_run": session.commands_run[:10],
        "turns_excerpt": turns,
    }


def _build_prompt(sessions: list[Session], folder: Path) -> str:
    data = [_session_excerpt(s) for s in sessions]
    agents = sorted({s.agent for s in sessions})
    return (
        "A developer worked on the same project folder using several different "
        "coding agents (Claude Code, Codex, Grok, ...), at different times. Below "
        "are summaries of each agent's most recent session in this folder. Decide "
        "which session represents the most recent REAL work worth continuing from. "
        "A session's newest message timestamp alone can be misleading -- e.g. a "
        "trivial side question can be the newest message in an otherwise stale "
        "session. Weigh the actual conversation content, the files it touched that "
        "still exist on disk, and the commands it ran.\n\n"
        f"Project folder: {folder}\n"
        f"Candidate agents: {', '.join(agents)}\n\n"
        "Sessions (JSON):\n"
        f"{json.dumps(data, indent=2)}\n\n"
        "Reply with ONLY a JSON object and nothing else, in this exact shape:\n"
        '{"agent": "<one of the candidate agents above>", '
        '"reason": "<one or two sentence explanation a developer would find useful>"}'
    )
