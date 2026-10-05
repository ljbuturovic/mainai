from datetime import datetime, timezone
from pathlib import Path

import pytest

from mainai import llm, llm_picker
from mainai.models import Session


def _session(agent: str, end_hour: int) -> Session:
    return Session(
        agent=agent,
        session_id=f"{agent}-1",
        cwd="/tmp/proj",
        start=datetime(2026, 1, 1, 0, tzinfo=timezone.utc),
        end=datetime(2026, 1, 1, end_hour, tzinfo=timezone.utc),
        title=f"{agent} session",
        turns=[],
    )


def test_single_session_skips_llm(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("llm.call should not be invoked for a single session")

    monkeypatch.setattr(llm, "call", fail)
    sessions = [_session("claude", 1)]
    result = llm_picker.llm_pick(sessions, Path("/tmp/proj"))
    assert result.session is sessions[0]


def test_falls_back_to_heuristic_on_llm_error(monkeypatch):
    def raise_error(*a, **k):
        raise llm.LLMError("claude not found")

    monkeypatch.setattr(llm, "call", raise_error)
    sessions = [_session("claude", 1), _session("codex", 2)]
    result = llm_picker.llm_pick(sessions, Path("/tmp/proj"))
    assert result.session is not None
    assert "LLM pick unavailable" in result.reasons[0]


def test_falls_back_on_unparseable_response(monkeypatch):
    monkeypatch.setattr(llm, "call", lambda *a, **k: "not json")
    sessions = [_session("claude", 1), _session("codex", 2)]
    result = llm_picker.llm_pick(sessions, Path("/tmp/proj"))
    assert result.session is not None
    assert "LLM pick unavailable" in result.reasons[0]


def test_uses_llm_choice(monkeypatch):
    monkeypatch.setattr(
        llm, "call", lambda *a, **k: '{"agent": "codex", "reason": "it did the real work"}'
    )
    sessions = [_session("claude", 1), _session("codex", 2)]
    result = llm_picker.llm_pick(sessions, Path("/tmp/proj"))
    assert result.session.agent == "codex"
    assert result.reasons == ["it did the real work"]


def test_falls_back_on_unrecognized_agent(monkeypatch):
    monkeypatch.setattr(llm, "call", lambda *a, **k: '{"agent": "grok", "reason": "x"}')
    sessions = [_session("claude", 1), _session("codex", 2)]
    result = llm_picker.llm_pick(sessions, Path("/tmp/proj"))
    assert result.session is not None
    assert "unrecognized agent" in result.reasons[0]
