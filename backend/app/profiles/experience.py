"""Total experience counted from the dates of the roles in the verified profile (e.g. July 2023 – Present).

Overlapping roles are merged so parallel jobs aren't double counted, and a current role counts up to today,
so the number stays right without the user editing it. If any role has no start date the dates can't tell
the whole story, and the user's own figure is kept.
"""

import re
from datetime import date

MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
NOW_WORDS = {"present", "current", "now", "till date", "today", "ongoing"}


def parse_month(value: str | None, *, end: bool = False) -> tuple[int, int] | None:
    """'2023-07', '2023-07-15', 'Jul 2023', 'July 2023', '07/2023', '2023' -> (year, month)."""
    s = (value or "").strip().lower()
    if not s:
        return None
    if s in NOW_WORDS:
        t = date.today()
        return t.year, t.month
    m = re.match(r"^(\d{4})[-/.](\d{1,2})", s)
    if m:
        return int(m.group(1)), max(1, min(12, int(m.group(2))))
    m = re.match(r"^(\d{1,2})[-/.](\d{4})$", s)
    if m:
        return int(m.group(2)), max(1, min(12, int(m.group(1))))
    m = re.match(r"^([a-z]{3})[a-z]*\.?[\s,'-]*(\d{2,4})$", s)
    if m and m.group(1) in MONTHS:
        y = int(m.group(2))
        return (y + 2000 if y < 100 else y), MONTHS[m.group(1)]
    m = re.match(r"^(\d{4})$", s)
    if m:
        return int(m.group(1)), 12 if end else 1
    return None


def years_from_roles(roles) -> float | None:
    """Total years across roles with dates, overlaps merged; None if any role lacks a start date."""
    spans = []
    for r in roles:
        start = parse_month(getattr(r, "start_date", None))
        if not start:
            return None
        if getattr(r, "is_current", False) or not getattr(r, "end_date", None):
            t = date.today()
            stop = (t.year, t.month)
        else:
            stop = parse_month(r.end_date, end=True)
            if not stop:
                return None
        a, b = start[0] * 12 + start[1], stop[0] * 12 + stop[1] + 1  # inclusive of the last month
        if b > a:
            spans.append((a, b))
    if not spans:
        return None
    spans.sort()
    months, cur_a, cur_b = 0, *spans[0]
    for a, b in spans[1:]:
        if a <= cur_b:
            cur_b = max(cur_b, b)
        else:
            months += cur_b - cur_a
            cur_a, cur_b = a, b
    months += cur_b - cur_a
    return round(months / 12, 1)


def describe(years: float | None) -> str | None:
    if years is None:
        return None
    y, m = int(years), round((years - int(years)) * 12)
    if m == 12:
        y, m = y + 1, 0
    return f"{y} yr{'s' if y != 1 else ''}" + (f" {m} mo" if m else "")
