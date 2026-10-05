"""One reader per coding agent. Each exposes `sessions_for(folder)` and returns
a list of `mainai.models.Session`, filtered to sessions whose cwd is the given
folder or a subfolder of it. Readers must never crash on a malformed or
unrecognized log line -- skip it and move on.
"""

from __future__ import annotations

from pathlib import Path

from mainai.models import Session
from mainai.readers import claude_code, codex, grok

READERS = {
    "claude": claude_code.sessions_for,
    "codex": codex.sessions_for,
    "grok": grok.sessions_for,
}


def all_sessions_for(folder: Path) -> list[Session]:
    sessions: list[Session] = []
    for reader in READERS.values():
        sessions.extend(reader(folder))
    sessions.sort(key=lambda s: s.end, reverse=True)
    return sessions
