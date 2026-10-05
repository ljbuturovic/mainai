import json
from pathlib import Path
from urllib.parse import quote

from mainai.readers import grok


def _write_session(cwd_dir: Path, session_id: str, cwd: str, summary: dict, chat_events: list[dict]) -> None:
    session_dir = cwd_dir / session_id
    session_dir.mkdir(parents=True)
    full_summary = {"info": {"id": session_id, "cwd": cwd}, **summary}
    (session_dir / "summary.json").write_text(json.dumps(full_summary), encoding="utf-8")
    (session_dir / "chat_history.jsonl").write_text(
        "\n".join(json.dumps(e) for e in chat_events), encoding="utf-8"
    )


def test_reads_session_matching_folder(tmp_path, monkeypatch):
    target = tmp_path / "home" / "user" / "proj"
    target.mkdir(parents=True)
    sessions_root = tmp_path / "grok_sessions"
    cwd_dir = sessions_root / quote(str(target), safe="")
    cwd_dir.mkdir(parents=True)

    _write_session(
        cwd_dir,
        "sess-1",
        str(target),
        {
            "created_at": "2026-08-29T17:28:48.725078146Z",
            "updated_at": "2026-09-06T02:54:12.778593664Z",
            "generated_title": "Fix the thing",
        },
        [
            {"type": "system", "content": "you are grok"},
            {"type": "user", "content": [{"type": "text", "text": "<user_info>ignore me</user_info>"}]},
            {
                "type": "user",
                "content": [{"type": "text", "text": "<user_query>\nfix the bug\n</user_query>"}],
            },
            {
                "type": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "name": "write",
                        "arguments": json.dumps({"file_path": str(target / "a.py")}),
                    },
                    {
                        "name": "run_terminal_command",
                        "arguments": json.dumps({"command": "pytest"}),
                    },
                ],
            },
            {"type": "assistant", "content": "done, fixed it"},
        ],
    )

    monkeypatch.setattr(grok, "SESSIONS_DIR", sessions_root)

    sessions = grok.sessions_for(target)

    assert len(sessions) == 1
    session = sessions[0]
    assert session.agent == "grok"
    assert session.title == "Fix the thing"
    assert str(target / "a.py") in session.files_touched
    assert "pytest" in session.commands_run
    assert any(t.role == "user" and t.text == "fix the bug" for t in session.turns)
    assert all("ignore me" not in t.text for t in session.turns)


def test_resolves_relative_and_tilde_file_paths(tmp_path, monkeypatch):
    target = tmp_path / "home" / "user" / "proj"
    target.mkdir(parents=True)
    sessions_root = tmp_path / "grok_sessions"
    cwd_dir = sessions_root / quote(str(target), safe="")
    cwd_dir.mkdir(parents=True)

    _write_session(
        cwd_dir,
        "sess-2",
        str(target),
        {
            "created_at": "2026-01-01T00:00:00.000000000Z",
            "updated_at": "2026-01-01T01:00:00.000000000Z",
        },
        [
            {
                "type": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "name": "search_replace",
                        "arguments": json.dumps({"file_path": "relative.py"}),
                    }
                ],
            },
        ],
    )

    monkeypatch.setattr(grok, "SESSIONS_DIR", sessions_root)

    sessions = grok.sessions_for(target)

    assert len(sessions) == 1
    assert str(target / "relative.py") in sessions[0].files_touched


def test_skips_malformed_lines_without_crashing(tmp_path, monkeypatch):
    target = tmp_path / "home" / "user" / "proj"
    target.mkdir(parents=True)
    sessions_root = tmp_path / "grok_sessions"
    cwd_dir = sessions_root / quote(str(target), safe="")
    session_dir = cwd_dir / "sess-3"
    session_dir.mkdir(parents=True)
    (session_dir / "summary.json").write_text(
        json.dumps(
            {
                "info": {"id": "sess-3", "cwd": str(target)},
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T01:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (session_dir / "chat_history.jsonl").write_text(
        "not json\n" + json.dumps({"type": "unknown-type"}), encoding="utf-8"
    )

    monkeypatch.setattr(grok, "SESSIONS_DIR", sessions_root)

    sessions = grok.sessions_for(target)
    assert len(sessions) == 1


def test_excludes_sessions_outside_folder(tmp_path, monkeypatch):
    target = tmp_path / "home" / "user" / "proj"
    target.mkdir(parents=True)
    other = tmp_path / "other"
    other.mkdir()
    sessions_root = tmp_path / "grok_sessions"
    cwd_dir = sessions_root / quote(str(other), safe="")
    cwd_dir.mkdir(parents=True)

    _write_session(
        cwd_dir,
        "sess-4",
        str(other),
        {"created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T01:00:00Z"},
        [],
    )

    monkeypatch.setattr(grok, "SESSIONS_DIR", sessions_root)

    assert grok.sessions_for(target) == []
