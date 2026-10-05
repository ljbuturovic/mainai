"""Reader for Grok CLI session logs.

Layout: ~/.grok/sessions/<url-encoded-cwd>/<session-uuid>/, each holding
summary.json (cwd, timestamps, generated title -- cheap to read, no need to
scan chat_history.jsonl just for metadata) and chat_history.jsonl (messages;
first line is the system prompt). Undocumented and version-dependent;
unrecognized line types and payload shapes are skipped.

A real user prompt is wrapped in <user_query>...</user_query> tags; the
first "user" message and some others are synthetic context (<user_info>,
<system-reminder>) that get skipped. Edit tools seen so far are `write` and
`search_replace`, both carrying a `file_path` argument -- which, per Grok's
own system prompt ("prefer relative paths"), may be relative, `~`-prefixed,
or absolute, so paths are resolved against the session's cwd before being
recorded.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote

from mainai.models import Session, Turn
from mainai.timeutil import parse_timestamp

SESSIONS_DIR = Path.home() / ".grok" / "sessions"

EDIT_TOOLS = {"write", "search_replace"}
USER_QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL)


def sessions_for(folder: Path) -> list[Session]:
    folder = folder.resolve()
    if not SESSIONS_DIR.is_dir():
        return []

    sessions = []
    for cwd_dir in SESSIONS_DIR.iterdir():
        if not cwd_dir.is_dir():
            continue
        for session_dir in cwd_dir.iterdir():
            if not session_dir.is_dir():
                continue
            session = _read_session(session_dir, cwd_dir.name, folder)
            if session is not None:
                sessions.append(session)
    return sessions


def _read_session(session_dir: Path, encoded_cwd: str, folder: Path) -> Session | None:
    summary_path = session_dir / "summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(summary, dict):
        return None

    info = summary.get("info") or {}
    cwd = info.get("cwd") or unquote(encoded_cwd)
    session_id = info.get("id") or session_dir.name

    cwd_path = Path(cwd).resolve()
    if cwd_path != folder and folder not in cwd_path.parents:
        return None

    start = parse_timestamp(summary.get("created_at"))
    end = parse_timestamp(summary.get("updated_at")) or parse_timestamp(
        summary.get("last_active_at")
    )
    if start is None or end is None:
        return None

    title = summary.get("generated_title") or summary.get("session_summary")
    turns, files_touched, commands_run = _read_chat_history(
        session_dir / "chat_history.jsonl", cwd
    )

    return Session(
        agent="grok",
        session_id=session_id,
        cwd=cwd,
        start=start,
        end=end,
        title=title,
        turns=turns,
        files_touched=files_touched,
        commands_run=commands_run,
    )


def _read_chat_history(path: Path, cwd: str) -> tuple[list[Turn], set[str], list[str]]:
    turns: list[Turn] = []
    files_touched: set[str] = set()
    commands_run: list[str] = []

    if not path.is_file():
        return turns, files_touched, commands_run

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return turns, files_touched, commands_run

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

        event_type = event.get("type")

        if event_type == "user":
            text = _extract_text(event.get("content"))
            match = USER_QUERY_RE.search(text)
            if match and match.group(1).strip():
                turns.append(Turn(role="user", text=match.group(1).strip()))
        elif event_type == "assistant":
            text = _extract_text(event.get("content"))
            if text.strip():
                turns.append(Turn(role="assistant", text=text.strip()))
            for tool_call in event.get("tool_calls") or []:
                if not isinstance(tool_call, dict):
                    continue
                name = tool_call.get("name")
                try:
                    arguments = json.loads(tool_call.get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                if name in EDIT_TOOLS:
                    file_path = arguments.get("file_path")
                    if file_path:
                        files_touched.add(_resolve_path(file_path, cwd))
                elif name == "run_terminal_command":
                    command = arguments.get("command")
                    if command:
                        commands_run.append(command)

    return turns, files_touched, commands_run


def _extract_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _resolve_path(file_path: str, cwd: str) -> str:
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = Path(cwd) / path
    return str(path)
