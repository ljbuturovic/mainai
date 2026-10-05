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

    @property
    def summary(self) -> str:
        if self.title:
            return self.title
        for turn in self.turns:
            if turn.role == "user" and turn.text.strip():
                return turn.text.strip().splitlines()[0][:80]
        return "(no prompt text found)"
