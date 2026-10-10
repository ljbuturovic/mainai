from datetime import datetime, timezone

from mainai.models import Session, Turn


def _session(turns: list[Turn], title: str | None = None) -> Session:
    return Session(
        agent="codex",
        session_id="s1",
        cwd="/tmp/proj",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        title=title,
        turns=turns,
    )


def test_title_wins_over_turns():
    session = _session([Turn(role="user", text="the original long-ago request")], title="A real title")
    assert session.summary == "A real title"


def test_no_title_uses_most_recent_substantial_user_turn():
    # Regression: a long-running Codex session (no title mechanism) was
    # quoting its first turn from months ago as "latest work".
    session = _session(
        [
            Turn(role="user", text="Create a python app that works like this: ..."),
            Turn(role="assistant", text="done"),
            Turn(role="user", text="Can you just add the stats to --strict stdout?"),
        ]
    )
    assert session.summary == "Can you just add the stats to --strict stdout?"


def test_trailing_trivial_acknowledgment_is_skipped():
    session = _session(
        [
            Turn(role="user", text="Please refactor the clustering code for readability"),
            Turn(role="assistant", text="done"),
            Turn(role="user", text="thanks"),
        ]
    )
    assert session.summary == "Please refactor the clustering code for readability"


def test_falls_back_to_first_turn_when_all_are_trivial():
    session = _session([Turn(role="user", text="ok"), Turn(role="user", text="yep")])
    assert session.summary == "ok"


def test_no_user_turns_at_all():
    session = _session([Turn(role="assistant", text="(nothing from the user)")])
    assert session.summary == "(no prompt text found)"


def test_only_first_line_of_a_multiline_turn_is_used():
    session = _session([Turn(role="user", text="Can you fix the bug?\nHere is a long traceback...")])
    assert session.summary == "Can you fix the bug?"


def test_trailing_pasted_log_is_skipped_in_favor_of_the_real_request():
    # Regression: a user pasted terminal/build output as their most recent
    # substantial turn; it shouldn't win over an earlier real request just
    # because it's long.
    session = _session(
        [
            Turn(role="user", text="Remind me how to start Expo"),
            Turn(role="assistant", text="run npx expo start"),
            Turn(role="user", text="I got a terrible stacktrace. Can you see it"),
            Turn(
                role="user",
                text="Logs for your project will appear below. Press Ctrl+C to exit.\n"
                + "\n".join(f"line {i}" for i in range(20)),
            ),
            Turn(role="assistant", text="found the bug"),
            Turn(role="user", text="Works now :-)"),
        ]
    )
    assert session.summary == "I got a terrible stacktrace. Can you see it"


def test_falls_back_to_a_paste_when_nothing_else_is_substantial():
    session = _session(
        [
            Turn(role="user", text="ok"),
            Turn(
                role="user",
                text="some long pasted log\n" + "\n".join(f"line {i}" for i in range(20)),
            ),
        ]
    )
    assert session.summary == "some long pasted log"
