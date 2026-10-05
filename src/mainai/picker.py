"""Heuristic, LLM-free picker: file evidence + git history only.

This is no longer mainai's default decision maker -- see `llm_picker` for
that, which asks an LLM to read the actual session content. This module is
kept as the free, instant path for `--list`, and as the fallback when the
LLM call fails or isn't available.

Raw "latest message" can mislead -- a trivial side question can be the
newest turn. The stronger signal is file evidence: does a file the session
touched still exist on disk, matching what the session wrote. Git history is
used as a secondary cross-check when the folder is a repo.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mainai.models import Session


@dataclass
class Pick:
    session: Session | None
    reasons: list[str]


def heuristic_pick(sessions: list[Session], folder: Path) -> Pick:
    if not sessions:
        return Pick(session=None, reasons=["no sessions found for this folder"])

    folder = folder.resolve()
    latest_commit_ts = _latest_git_commit_timestamp(folder)

    scored = []
    for session in sessions:
        existing = {f for f in session.files_touched if Path(f).exists()}
        scored.append((session, bool(existing), len(existing)))

    scored.sort(key=lambda item: (item[1], item[2], item[0].end), reverse=True)
    best_session, has_evidence, existing_count = scored[0]

    reasons = []
    if has_evidence:
        reasons.append(f"{existing_count} file(s) it touched still exist on disk")
    else:
        reasons.append("no session has file evidence on disk; picked by latest activity")
    reasons.append(f"most recent turn {best_session.end.isoformat()}")

    if latest_commit_ts is not None:
        if best_session.start <= latest_commit_ts <= best_session.end:
            reasons.append("its time range contains the latest git commit")
        else:
            reasons.append(f"latest git commit was at {latest_commit_ts.isoformat()}")

    return Pick(session=best_session, reasons=reasons)


def _latest_git_commit_timestamp(folder: Path) -> datetime | None:
    if not (folder / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(folder), "log", "-1", "--format=%cI"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    value = result.stdout.strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
