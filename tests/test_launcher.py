import platform

import pytest

from mainai import launcher


def test_windows_is_refused(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    with pytest.raises(launcher.LaunchError, match="Windows"):
        launcher.launch("claude", "/tmp")


def test_unknown_agent_is_refused(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    with pytest.raises(launcher.LaunchError, match="gemini"):
        launcher.launch("gemini", "/tmp")


def test_missing_binary_is_refused(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    with pytest.raises(launcher.LaunchError, match="not found on PATH"):
        launcher.launch("claude", "/tmp")


def test_claude_uses_continue_flag(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(launcher.shutil, "which", lambda name: f"/usr/bin/{name}")

    captured = {}

    def fake_run(args, cwd):
        captured["args"] = args
        captured["cwd"] = cwd

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)

    rc = launcher.launch("claude", "/some/project")

    assert rc == 0
    assert captured["args"] == ["claude", "-c", launcher.HANDOFF_PROMPT]
    assert captured["cwd"] == "/some/project"


def test_codex_uses_resume_last_not_dash_c(monkeypatch):
    # codex's own -c means --config, not continue -- must not reuse it.
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(launcher.shutil, "which", lambda name: f"/usr/bin/{name}")

    captured = {}

    def fake_run(args, cwd):
        captured["args"] = args

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)

    launcher.launch("codex", "/some/project")

    assert captured["args"] == ["codex", "resume", "--last", launcher.HANDOFF_PROMPT]
    assert "-c" not in captured["args"]


def test_grok_uses_continue_flag(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(launcher.shutil, "which", lambda name: f"/usr/bin/{name}")

    captured = {}

    def fake_run(args, cwd):
        captured["args"] = args

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)

    launcher.launch("grok", "/some/project")

    assert captured["args"] == ["grok", "-c", launcher.HANDOFF_PROMPT]


def test_propagates_exit_code(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(launcher.shutil, "which", lambda name: f"/usr/bin/{name}")

    class Result:
        returncode = 7

    monkeypatch.setattr(launcher.subprocess, "run", lambda args, cwd: Result())

    assert launcher.launch("claude", "/tmp") == 7
