"""Reader for Claude Code's own transcripts.

Format: JSONL under ~/.claude/projects/<cwd-slug>/<session-id>.jsonl, one
event per line. `cwd`, `timestamp`, `sessionId` appear on most event types.
The format is undocumented and has grown new event types across versions
(mode, permission-mode, file-history-snapshot, attachment, ai-title, ...);
this reader only looks at the few types it understands and skips the rest.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from mainai.models import Session, Turn

PROJECTS_DIR = Path.home() / ".claude" / "projects"

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}


def sessions_for(folder: Path) -> list[Session]:
    folder = folder.resolve()
    if not PROJECTS_DIR.is_dir():
        return []

    sessions = []
    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_path in project_dir.glob("*.jsonl"):
            session = _read_session(jsonl_path, folder)
            if session is not None:
                sessions.append(session)
    return sessions


def _read_session(path: Path, folder: Path) -> Session | None:
    session_id = path.stem
    cwd: str | None = None
    title: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    turns: list[Turn] = []
    files_touched: set[str] = set()
    commands_run: list[str] = []

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue

        event_cwd = event.get("cwd")
        if event_cwd:
            cwd = event_cwd

        ts = _parse_timestamp(event.get("timestamp"))
        if ts is not None:
            if start is None or ts < start:
                start = ts
            if end is None or ts > end:
                end = ts

        event_type = event.get("type")

        if event_type == "ai-title":
            title = event.get("aiTitle") or title
            continue

        if event_type not in ("user", "assistant"):
            continue

        message = event.get("message")
        if not isinstance(message, dict):
            continue
        role = message.get("role", event_type)
        content = message.get("content")

        if isinstance(content, str):
            if not event.get("isMeta") and content.strip():
                turns.append(Turn(role=role, text=content, timestamp=ts))
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "text" and not event.get("isMeta"):
                    text = block.get("text", "")
                    if text.strip():
                        turns.append(Turn(role=role, text=text, timestamp=ts))
                elif block_type == "tool_use":
                    name = block.get("name")
                    tool_input = block.get("input") or {}
                    if name in EDIT_TOOLS:
                        file_path = tool_input.get("file_path")
                        if file_path:
                            files_touched.add(file_path)
                    elif name == "Bash":
                        command = tool_input.get("command")
                        if command:
                            commands_run.append(command)

    if cwd is None or start is None or end is None:
        return None

    cwd_path = Path(cwd).resolve()
    if cwd_path != folder and folder not in cwd_path.parents:
        return None

    return Session(
        agent="claude",
        session_id=session_id,
        cwd=cwd,
        start=start,
        end=end,
        title=title,
        turns=turns,
        files_touched=files_touched,
        commands_run=commands_run,
    )


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
