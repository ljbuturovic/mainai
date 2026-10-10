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

    @property
    def summary(self) -> str:
        if self.title:
            return self.title
        # No title (e.g. Codex has no title mechanism at all): fall back to
        # a user turn's text. A single mainai session can span weeks or
        # months of back-and-forth, so the FIRST turn can be long stale --
        # scan from the end for the most recent turn worth quoting, only
        # falling further back past a trivial trailing "ok"/"thanks".
        substantial = [
            turn
            for turn in self.turns
            if turn.role == "user" and len(turn.text.strip()) >= self.MIN_SUMMARY_TURN_CHARS
        ]
        if substantial:
            return substantial[-1].text.strip().splitlines()[0].rstrip()[:80]
        for turn in self.turns:
            if turn.role == "user" and turn.text.strip():
                return turn.text.strip().splitlines()[0].rstrip()[:80]
        return "(no prompt text found)"
