"""Common record types every per-agent reader converts its log format into."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    text: str
    timestamp: datetime | None = None


@dataclass
class Session:
    agent: str  # "claude", "codex", "grok", ...
    session_id: str
    cwd: str
    start: datetime
    end: datetime
    title: str | None = None
    turns: list[Turn] = field(default_factory=list)
    files_touched: set[str] = field(default_factory=set)
    commands_run: list[str] = field(default_factory=list)

    # Below this length, a user turn is treated as a trivial acknowledgment
    # ("ok", "thanks", "lgtm") rather than something worth quoting.
    MIN_SUMMARY_TURN_CHARS = 15
    # More newlines than this and a turn is treated as a pasted log/stack
    # trace/command output rather than a short request. A real request
    # occasionally wraps around a short inline example or table (seen in
    # real data up to 6 newlines); a genuine pasted build log/traceback
    # runs much higher (seen in real data: 10-75 newlines). There's a
    # clean gap between those two clusters, hence 8.
    MAX_SUMMARY_TURN_NEWLINES = 8

    @property
    def summary(self) -> str:
        if self.title:
            return self.title

        # No title (e.g. Codex has no title mechanism at all): fall back to
        # a user turn's text. A single mainai session can span weeks or
        # months of back-and-forth, so the FIRST turn can be long stale --
        # scan from the end for the most recent turn worth quoting, falling
        # back past a trivial trailing "ok"/"thanks" or a pasted log/
        # traceback the user included with a real request.
        user_turns = [turn for turn in self.turns if turn.role == "user" and turn.text.strip()]
        if not user_turns:
            return "(no prompt text found)"

        def is_substantial(turn: Turn) -> bool:
            return len(turn.text.strip()) >= self.MIN_SUMMARY_TURN_CHARS

        def looks_like_a_paste(turn: Turn) -> bool:
            return turn.text.count("\n") > self.MAX_SUMMARY_TURN_NEWLINES

        for turn in reversed(user_turns):
            if is_substantial(turn) and not looks_like_a_paste(turn):
                return turn.text.strip().splitlines()[0].rstrip()[:80]

        for turn in reversed(user_turns):
            if is_substantial(turn):
                return turn.text.strip().splitlines()[0].rstrip()[:80]

        return user_turns[0].text.strip().splitlines()[0].rstrip()[:80]
