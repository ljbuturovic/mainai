import pytest

from mainai import continue_command as cc


def test_unknown_agent_is_refused():
    with pytest.raises(cc.UnknownAgentError, match="gemini"):
        cc.continue_command("gemini")


def test_claude_uses_continue_flag():
    assert cc.continue_command("claude") == ["claude", "-c", cc.HANDOFF_PROMPT]


def test_codex_uses_resume_last_not_dash_c():
    # codex's own -c means --config, not continue -- must not reuse it.
    args = cc.continue_command("codex")
    assert args == ["codex", "resume", "--last", cc.HANDOFF_PROMPT]
    assert "-c" not in args


def test_grok_uses_continue_flag():
    assert cc.continue_command("grok") == ["grok", "-c", cc.HANDOFF_PROMPT]


def test_format_command_quotes_the_prompt():
    formatted = cc.format_command(["claude", "-c", cc.HANDOFF_PROMPT])
    assert formatted.startswith("claude -c ")
    assert cc.HANDOFF_PROMPT in formatted
    # the prompt has spaces, so it must come through as one shell token
    assert formatted.count("'") >= 2 or '"' in formatted
