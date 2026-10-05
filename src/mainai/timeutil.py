"""Shared timestamp parsing for reader modules.

Different agents emit different fractional-second precision (milliseconds,
microseconds, nanoseconds), which `datetime.fromisoformat` only accepts up
to microseconds. Truncate before parsing instead of failing on it.
"""

from __future__ import annotations

import re
from datetime import datetime

_FRACTION_RE = re.compile(r"\.(\d+)")


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    value = value.replace("Z", "+00:00")
    value = _FRACTION_RE.sub(lambda m: "." + m.group(1)[:6], value, count=1)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
