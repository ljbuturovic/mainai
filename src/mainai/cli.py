"""mainai -- pick which coding agent to continue a project with."""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

from mainai import __version__, llm
from mainai.launcher import LaunchError, launch
from mainai.llm_picker import llm_pick
from mainai.picker import Pick, heuristic_pick
from mainai.readers import READERS, all_sessions_for
from mainai.summarizer import write_handoff

REASON_WIDTH = 78


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mainai",
        description=(
            "Find which coding agent (Claude Code, Codex, ...) last did real "
            "work in a project folder, and show which one to continue with."
        ),
    )
    parser.add_argument(
        "folder",
        help="project folder to inspect, e.g. `.` for the current directory",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help=(
            "show the sessions found and a quick file-evidence guess, nothing "
            "else (no file written, no LLM call)"
        ),
    )
    parser.add_argument(
        "--agent",
        metavar="NAME",
        help="override the pick, e.g. --agent codex (no LLM call)",
    )
    parser.add_argument(
        "--handoff",
        action="store_true",
        help=(
            "summarize the other agents' sessions into HANDOFF.md (uses an "
            "LLM), then launch the picked agent, continuing its most recent "
            "conversation and pointing it at HANDOFF.md. Linux/macOS only."
        ),
    )
    parser.add_argument(
        "--handoff-agents",
        metavar="AGENT[,AGENT...]",
        help=(
            "with --handoff, summarize only these agents' sessions into "
            "HANDOFF.md instead of every agent other than the one picked "
            "(comma-separated, e.g. --handoff-agents grok). Implies --handoff, "
            "but does NOT launch anything -- useful to continue with one "
            "agent (--agent) while still pulling in context from a specific "
            "other one, without mainai launching either of them for you."
        ),
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=(
            "don't ask for confirmation before an LLM call that would bill "
            "ANTHROPIC_API_KEY directly (no claude.ai subscription login found)"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _print_reasons(reasons: list[str]) -> None:
    if len(reasons) == 1:
        print(
            textwrap.fill(
                reasons[0], width=REASON_WIDTH, initial_indent="  ", subsequent_indent="  "
            )
        )
        return
    for reason in reasons:
        print(
            textwrap.fill(
                reason, width=REASON_WIDTH, initial_indent="  - ", subsequent_indent="    "
            )
        )


def _confirm_api_key_billing(yes: bool) -> bool:
    print(
        "mainai: no claude.ai subscription login found; the LLM pick would bill "
        "ANTHROPIC_API_KEY directly (pay-per-token), not a subscription.",
        file=sys.stderr,
    )
    if yes:
        return True
    if not sys.stdin.isatty():
        print(
            "mainai: not an interactive terminal; re-run with --yes to proceed anyway, "
            "or use --list / --agent to avoid the LLM call.",
            file=sys.stderr,
        )
        return False
    reply = input("Proceed and bill ANTHROPIC_API_KEY for this call? [y/N] ").strip().lower()
    return reply in ("y", "yes")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        # No arguments at all: print help and do nothing, rather than
        # erroring on the missing required `folder` argument or, worse,
        # silently processing the current directory -- the default pick
        # calls an LLM, and a stray bare `mainai` right after install
        # should never spend tokens or bill an API key unasked.
        parser.print_help()
        return 0
    args = parser.parse_args(argv)

    handoff_agents: set[str] | None = None
    if args.handoff_agents:
        handoff_agents = {name.strip() for name in args.handoff_agents.split(",") if name.strip()}
        unknown = sorted(handoff_agents - set(READERS))
        if unknown:
            print(
                f"mainai: unknown agent(s) in --handoff-agents: {', '.join(unknown)} "
                f"(known: {', '.join(sorted(READERS))})",
                file=sys.stderr,
            )
            return 1
    handoff_requested = args.handoff or handoff_agents is not None

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"mainai: {folder} is not a directory", file=sys.stderr)
        return 1

    sessions = all_sessions_for(folder)

    if not sessions:
        print(f"No sessions found for {folder.resolve()}")
        return 0

    needs_llm = handoff_requested or not (args.list or args.agent)
    if needs_llm:
        auth_mode = llm.determine_auth_mode()
        if auth_mode == llm.AuthMode.UNAVAILABLE:
            print(
                "mainai: no usable `claude` auth found (no claude.ai login, no "
                "ANTHROPIC_API_KEY). Run `claude login`, or use --list / --agent "
                "to avoid the LLM call.",
                file=sys.stderr,
            )
            return 1
        if auth_mode == llm.AuthMode.API_KEY and not _confirm_api_key_billing(args.yes):
            print("mainai: aborted.", file=sys.stderr)
            return 1

    if args.agent:
        chosen = next((s for s in sessions if s.agent == args.agent), None)
        if chosen is None:
            print(f"mainai: no session found for agent '{args.agent}'", file=sys.stderr)
            return 1
        result = Pick(session=chosen, reasons=[f"overridden with --agent {args.agent}"])
    elif args.list:
        result = heuristic_pick(sessions, folder)
    else:
        result = llm_pick(sessions, folder)

    chosen = result.session

    print(f"Found {len(sessions)} session(s) in {folder.resolve()}")
    for session in sessions:
        marker = "  <- latest work" if session is chosen else ""
        print(f'  {session.agent:<8} {session.end.date()}  "{session.summary}"{marker}')

    if args.list:
        if handoff_requested:
            print("mainai: --handoff has no effect with --list", file=sys.stderr)
        return 0

    if chosen is None:
        return 0

    print()
    print(f"Continue with: {chosen.agent}")
    _print_reasons(result.reasons)
    print()
    print(f"  Advice: cd {chosen.cwd} && {chosen.agent}")

    if handoff_requested:
        try:
            path = write_handoff(sessions, chosen, folder, only_agents=handoff_agents)
        except ValueError as exc:
            print(f"mainai: {exc}", file=sys.stderr)
            return 1
        except llm.LLMError as exc:
            print(f"mainai: could not write HANDOFF.md: {exc}", file=sys.stderr)
            return 1
        print(f"Wrote {path}")

        # --handoff-agents narrows what gets summarized but never launches
        # anything, even if --handoff was also passed alongside it.
        if args.handoff and handoff_agents is None:
            try:
                return launch(chosen.agent, chosen.cwd)
            except LaunchError as exc:
                print(f"mainai: {exc}", file=sys.stderr)
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
