"""mainai -- pick which coding agent to continue a project with."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mainai import __version__, llm
from mainai.llm_picker import llm_pick
from mainai.picker import Pick, heuristic_pick
from mainai.readers import all_sessions_for
from mainai.summarizer import write_handoff


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
        help="also summarize the other agents' sessions into HANDOFF.md (uses an LLM)",
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

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"mainai: {folder} is not a directory", file=sys.stderr)
        return 1

    sessions = all_sessions_for(folder)

    if not sessions:
        print(f"No sessions found for {folder.resolve()}")
        return 0

    needs_llm = args.handoff or not (args.list or args.agent)
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
        if args.handoff:
            print("mainai: --handoff has no effect with --list", file=sys.stderr)
        return 0

    if chosen is None:
        return 0

    print()
    print(f"Continue with: {chosen.agent} ({'; '.join(result.reasons)})")
    print(f"  Advice: cd {chosen.cwd} && {chosen.agent}")

    if args.handoff:
        try:
            path = write_handoff(sessions, chosen, folder)
        except ValueError:
            print("mainai: only one session found; nothing to hand off", file=sys.stderr)
            return 1
        except llm.LLMError as exc:
            print(f"mainai: could not write HANDOFF.md: {exc}", file=sys.stderr)
            return 1
        print(f"Wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
