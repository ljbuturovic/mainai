from datetime import datetime, timezone
from pathlib import Path

import pytest

from mainai import llm, summarizer
from mainai.models import Session, Turn


def _session(agent: str, session_id: str, end_hour: int, turns: list[Turn] | None = None) -> Session:
    return Session(
        agent=agent,
        session_id=session_id,
        cwd="/tmp/proj",
        start=datetime(2026, 1, 1, 0, tzinfo=timezone.utc),
        end=datetime(2026, 1, 1, end_hour, tzinfo=timezone.utc),
        title=f"{agent} session",
        turns=turns or [],
        files_touched={"a.py"},
        commands_run=["ls"],
    )


def test_raises_when_no_other_sessions(tmp_path):
    chosen = _session("claude", "c1", 1)
    with pytest.raises(ValueError):
        summarizer.write_handoff([chosen], chosen, tmp_path)


def test_writes_handoff_file(tmp_path, monkeypatch):
    chosen = _session("claude", "c1", 2)
    other = _session(
        "codex",
        "x1",
        1,
        turns=[Turn(role="user", text="fix the clustering bug")],
    )

    captured_prompt = {}

    def fake_call(prompt, **kwargs):
        captured_prompt["prompt"] = prompt
        return "## Done\n- (codex, 2026-01-01) fixed the clustering bug\n"

    monkeypatch.setattr(llm, "call", fake_call)

    path = summarizer.write_handoff([chosen, other], chosen, tmp_path)

    assert path == tmp_path / "HANDOFF.md"
    content = path.read_text(encoding="utf-8")
    assert "Continuing with **claude**" in content
    assert "## Done" in content
    assert "fixed the clustering bug" in content
    assert "codex" in captured_prompt["prompt"]
    assert "claude" not in captured_prompt["prompt"].split("Other sessions")[1]


def test_propagates_llm_error(tmp_path, monkeypatch):
    chosen = _session("claude", "c1", 2)
    other = _session("codex", "x1", 1)

    def raise_error(*a, **k):
        raise llm.LLMError("no claude CLI")

    monkeypatch.setattr(llm, "call", raise_error)

    with pytest.raises(llm.LLMError):
        summarizer.write_handoff([chosen, other], chosen, tmp_path)
