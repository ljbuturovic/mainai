import json
from pathlib import Path

from mainai.readers import claude_code


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")


def test_reads_session_matching_folder(tmp_path, monkeypatch):
    project_dir = tmp_path / "projects" / "-home-user-proj"
    project_dir.mkdir(parents=True)
    target = tmp_path / "home" / "user" / "proj"
    target.mkdir(parents=True)

    events = [
        {
            "type": "user",
            "message": {"role": "user", "content": "fix the bug"},
            "timestamp": "2026-01-01T00:00:00Z",
            "cwd": str(target),
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "done"},
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": str(target / "a.py")},
                    },
                ],
            },
            "timestamp": "2026-01-01T00:05:00Z",
            "cwd": str(target),
        },
        {"type": "ai-title", "aiTitle": "Fix the bug"},
    ]
    _write_jsonl(project_dir / "session1.jsonl", events)

    monkeypatch.setattr(claude_code, "PROJECTS_DIR", tmp_path / "projects")

    sessions = claude_code.sessions_for(target)

    assert len(sessions) == 1
    session = sessions[0]
    assert session.agent == "claude"
    assert session.title == "Fix the bug"
    assert str(target / "a.py") in session.files_touched
    assert any(t.text == "fix the bug" for t in session.turns)


def test_skips_malformed_lines_without_crashing(tmp_path, monkeypatch):
    project_dir = tmp_path / "projects" / "-home-user-proj"
    project_dir.mkdir(parents=True)
    target = tmp_path / "home" / "user" / "proj"
    target.mkdir(parents=True)

    path = project_dir / "session2.jsonl"
    path.write_text(
        "not json at all\n"
        + json.dumps({"type": "unknown-future-type", "stuff": 1})
        + "\n"
        + json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": "hello"},
                "timestamp": "2026-01-01T00:00:00Z",
                "cwd": str(target),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(claude_code, "PROJECTS_DIR", tmp_path / "projects")

    sessions = claude_code.sessions_for(target)

    assert len(sessions) == 1
    assert sessions[0].turns[0].text == "hello"


def test_excludes_sessions_outside_folder(tmp_path, monkeypatch):
    project_dir = tmp_path / "projects" / "-other"
    project_dir.mkdir(parents=True)
    other = tmp_path / "other"
    other.mkdir()
    target = tmp_path / "home" / "user" / "proj"
    target.mkdir(parents=True)

    _write_jsonl(
        project_dir / "session3.jsonl",
        [
            {
                "type": "user",
                "message": {"role": "user", "content": "unrelated"},
                "timestamp": "2026-01-01T00:00:00Z",
                "cwd": str(other),
            }
        ],
    )

    monkeypatch.setattr(claude_code, "PROJECTS_DIR", tmp_path / "projects")

    assert claude_code.sessions_for(target) == []
