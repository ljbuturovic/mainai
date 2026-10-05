"""Thin wrapper around calling an LLM in headless/non-interactive mode.

Default backend is `claude -p` (Claude Code headless mode): no separate API
key needed when the user has a claude.ai login, since it draws on that
login's included usage. Kept behind this small interface so `codex exec` or
`grok -p` can be swapped in later (see mainai.md).

Many developers keep ANTHROPIC_API_KEY set for their own API projects, and
`claude -p` prefers that key over a claude.ai login when both are present.
mainai must not silently bill someone's personal API key for a background
utility call, so every call here strips ANTHROPIC_API_KEY from the
subprocess environment whenever a claude.ai login is available
(`determine_auth_mode` -> AuthMode.SUBSCRIPTION). When no claude.ai login
exists, the caller (mainai.cli) must get explicit confirmation before a call
that will bill the API key.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from enum import Enum


class LLMError(RuntimeError):
    pass


class AuthMode(Enum):
    SUBSCRIPTION = "subscription"  # claude.ai login available; API key (if any) is stripped
    API_KEY = "api_key"  # no claude.ai login; a call would bill ANTHROPIC_API_KEY
    UNAVAILABLE = "unavailable"  # claude CLI missing, or no usable auth at all


def determine_auth_mode() -> AuthMode:
    if shutil.which("claude") is None:
        return AuthMode.UNAVAILABLE

    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    status: dict = {}
    try:
        result = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        status = json.loads(result.stdout)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        status = {}

    if status.get("loggedIn") and status.get("authMethod") == "claude.ai":
        return AuthMode.SUBSCRIPTION
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AuthMode.API_KEY
    return AuthMode.UNAVAILABLE


def call(prompt: str, *, model: str = "sonnet", timeout: int = 180) -> str:
    """Run `prompt` through `claude -p` and return the text result.

    Raises LLMError on anything that keeps the caller from getting a usable
    answer: missing CLI, process failure, timeout, or unparseable output.
    """
    if shutil.which("claude") is None:
        raise LLMError("the `claude` CLI is not on PATH")

    env = dict(os.environ)
    if determine_auth_mode() == AuthMode.SUBSCRIPTION:
        env.pop("ANTHROPIC_API_KEY", None)

    try:
        result = subprocess.run(
            [
                "claude",
                "-p",
                prompt,
                "--model",
                model,
                "--output-format",
                "json",
                "--no-session-persistence",
                "--tools",
                "",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.SubprocessError as exc:
        raise LLMError(f"failed to run claude -p: {exc}") from exc

    if result.returncode != 0:
        raise LLMError(f"claude -p exited {result.returncode}: {result.stderr.strip()}")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise LLMError(f"could not parse claude -p output as JSON: {exc}") from exc

    if payload.get("is_error"):
        raise LLMError(f"claude -p reported an error: {payload.get('result')}")

    text = payload.get("result")
    if not text:
        raise LLMError("claude -p returned no text result")
    return text
