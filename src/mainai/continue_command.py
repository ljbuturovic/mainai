"""The command to continue the picked agent's most recent conversation,
pointed at HANDOFF.md.

mainai only prints this -- it never executes it. An earlier version
launched the agent directly, but that was too intrusive to ship as default
behavior, so this module only builds and formats the command for display.
"""

from __future__ import annotations

import shlex

HANDOFF_PROMPT = "Read HANDOFF.md and integrate it into our existing conversation"

# Per-agent argv to continue its most recent conversation and feed it a new
# prompt. Verified against each CLI's own --help -- they are NOT uniform.
# Notably, codex's `-c` means `--config` (not continue), so it needs its
# `resume --last` subcommand instead of a `-c`/`--continue` flag.
_CONTINUE_ARGS = {
    "claude": lambda prompt: ["claude", "-c", prompt],
    "codex": lambda prompt: ["codex", "resume", "--last", prompt],
    "grok": lambda prompt: ["grok", "-c", prompt],
}


class UnknownAgentError(RuntimeError):
    pass


def continue_command(agent: str) -> list[str]:
    """Return the argv that continues `agent`'s most recent conversation
    and feeds it HANDOFF_PROMPT. Raises UnknownAgentError for an agent with
    no known continue command.
    """
    build_args = _CONTINUE_ARGS.get(agent)
    if build_args is None:
        raise UnknownAgentError(f"no continue command known for agent '{agent}'")
    return build_args(HANDOFF_PROMPT)


def format_command(args: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in args)
