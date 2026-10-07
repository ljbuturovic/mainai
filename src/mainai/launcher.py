"""Launch the picked agent, continuing its existing conversation and
pointing it at HANDOFF.md.

Linux/macOS only for now. These CLIs are commonly installed on Windows as
npm .cmd/.ps1 wrapper scripts rather than native .exe's, which Windows
can't exec directly -- it has to go through cmd.exe, which does its own
parsing of shell metacharacters before handing off to the wrapped program
(a well-known source of bugs in other tools' Windows launchers). That's
solvable, but untestable without a Windows machine, so it's left out
rather than shipped unverified.
"""

from __future__ import annotations

import platform
import shlex
import shutil
import subprocess

HANDOFF_PROMPT = "Read HANDOFF.md and integrate it into our existing conversation"

# Per-agent argv to continue its most recent conversation in the cwd and
# feed it a new prompt. Verified against each CLI's own --help -- they are
# NOT uniform. Notably, codex's `-c` means `--config` (not continue), so it
# needs its `resume --last` subcommand instead of a `-c`/`--continue` flag.
_CONTINUE_ARGS = {
    "claude": lambda prompt: ["claude", "-c", prompt],
    "codex": lambda prompt: ["codex", "resume", "--last", prompt],
    "grok": lambda prompt: ["grok", "-c", prompt],
}


class LaunchError(RuntimeError):
    pass


def launch(agent: str, cwd: str) -> int:
    """Launch `agent`, continuing its most recent conversation in `cwd` and
    feeding it HANDOFF_PROMPT. Returns the launched process's exit code.
    """
    if platform.system() == "Windows":
        raise LaunchError("launching isn't supported on Windows yet (Linux/macOS only)")

    build_args = _CONTINUE_ARGS.get(agent)
    if build_args is None:
        raise LaunchError(f"no launch command known for agent '{agent}'")

    args = build_args(HANDOFF_PROMPT)
    if shutil.which(args[0]) is None:
        raise LaunchError(f"'{args[0]}' not found on PATH")

    print(f"Launching: {' '.join(shlex.quote(a) for a in args)}")
    result = subprocess.run(args, cwd=cwd)
    return result.returncode
