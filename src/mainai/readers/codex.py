"""Reader for Codex CLI session logs.

Format: JSONL under ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl (or, when
Codex is installed via snap, ~/snap/codex/<rev>/sessions/YYYY/MM/DD/). First
line is `type: session_meta` with `payload.cwd`, `payload.id`,
`payload.timestamp`. Then `response_item` (message, function_call,
function_call_output, reasoning), `event_msg`, `turn_context`. Undocumented
and version-dependent; unrecognized line types and payload shapes are
skipped.

Codex has no dedicated "edit file" tool call in the sessions seen so far --
file edits happen via shell commands run through `exec_command` -- so
`files_touched` is left empty here; only `commands_run` is populated.
"""

from __future__ import annotations

import json
from pathlib import Path

from mainai.models import Session, Turn
from mainai.timeutil import parse_timestamp


def _session_bases() -> list[Path]:
    bases = [Path.home() / ".codex" / "sessions"]
    snap_root = Path.home() / "snap" / "codex"
    if snap_root.is_dir():
        for rev_dir in snap_root.iterdir():
            candidate = rev_dir / "sessions"
            if candidate.is_dir():
                bases.append(candidate)
    return bases


def sessions_for(folder: Path) -> list[Session]:
    folder = folder.resolve()
    sessions = []
    for base in _session_bases():
        if not base.is_dir():
            continue
        for jsonl_path in base.glob("*/*/*/rollout-*.jsonl"):
            session = _read_session(jsonl_path, folder)
            if session is not None:
                sessions.append(session)
    return sessions


def _read_session(path: Path, folder: Path) -> Session | None:
    session_id: str | None = None
    cwd: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    turns: list[Turn] = []
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

        ts = parse_timestamp(event.get("timestamp"))
        if ts is not None:
            if start is None or ts < start:
                start = ts
            if end is None or ts > end:
                end = ts

        event_type = event.get("type")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue

        if event_type == "session_meta":
            session_id = payload.get("id") or payload.get("session_id") or session_id
            cwd = payload.get("cwd") or cwd
            continue

        if event_type != "response_item":
            continue

        item_type = payload.get("type")

        if item_type == "message":
            role = payload.get("role")
            if role not in ("user", "assistant"):
                continue
            content = payload.get("content")
            if not isinstance(content, list):
                continue
            text = "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict)
                and block.get("type") in ("input_text", "output_text", "text")
            ).strip()
            if not text or text.startswith("<environment_context>"):
                continue
            turns.append(Turn(role=role, text=text, timestamp=ts))
        elif item_type == "function_call" and payload.get("name") == "exec_command":
            try:
                arguments = json.loads(payload.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            command = arguments.get("cmd")
            if command:
                commands_run.append(command)

    if session_id is None or cwd is None or start is None or end is None:
        return None

    cwd_path = Path(cwd).resolve()
    if cwd_path != folder and folder not in cwd_path.parents:
        return None

    return Session(
        agent="codex",
        session_id=session_id,
        cwd=cwd,
        start=start,
        end=end,
        turns=turns,
        commands_run=commands_run,
    )
