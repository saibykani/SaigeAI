"""Parse a pasted CTC breakup (offer letter table or message) into calculator fields. Numbers are only read, never invented."""

import re

_NUM = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(lpa|lakhs?|lacs?|l\b|k\b|cr\b|crores?)?", re.I)
_PER_MONTH = re.compile(r"per\s*month|/\s*month|\bp\.?m\.?\b|monthly|per\s*mth|/\s*mo\b", re.I)

# Order matters: the first rule that matches a line's label wins. An empty field name means "ignore this line".
RULES: list[tuple[str, str]] = [
    (r"employer.*(pf|provident)|(pf|provident).*employer", "employer_pf"),
    (r"employee.*(pf|provident)|(pf|provident).*employee", ""),
    (r"joining|sign[- ]?on|signing|relocation|retention", "joining_bonus"),
    (r"esop|rsu|stock|equity", "esop_annual"),
    (r"nps|national pension", "employer_nps"),
    (r"variable|bonus|incentive|performance|pli\b", "variable"),
    (r"gratuity", "gratuity"),
    (r"insurance|mediclaim|medical", "insurance"),
    (r"\bhra\b|house rent", "hra"),
    (r"basic", "basic"),
    (r"special|flexi|flexible", "special"),
    (r"\blta\b|leave travel", "lta"),
    (r"total ctc|\bctc\b|cost to company|total compensation|package", "ctc"),
    (r"conveyance|allowance|food|meal|telephone|phone|internet|wellness|other", "other_allowances"),
]


def _value(num: str, unit: str | None) -> float:
    v = float(num.replace(",", ""))
    u = (unit or "").lower().strip()
    if u in ("lpa", "l") or u.startswith(("lakh", "lac")):
        return v * 100_000
    if u == "k":
        return v * 1000
    if u == "cr" or u.startswith("crore"):
        return v * 10_000_000
    return v


def parse_breakup(text: str) -> dict:
    fields: dict[str, float] = {}
    ctc = None
    unmatched: list[str] = []
    for raw in text.splitlines():
        line = raw.strip(" \t|-*•")
        if not line:
            continue
        label = re.split(r"[\d₹]", line, maxsplit=1)[0].lower()
        nums = [_value(m.group(1), m.group(2)) for m in _NUM.finditer(line)]
        if not label.strip() or not nums:
            continue
        key = next((f for pat, f in RULES if re.search(pat, label)), None)
        if key is None:
            unmatched.append(raw.strip())
            continue
        if not key:
            continue
        amount = max(nums)
        if _PER_MONTH.search(line) and len(nums) == 1:
            amount *= 12
        if key == "ctc":
            ctc = amount
        else:
            fields[key] = fields.get(key, 0.0) + amount
    return {"fields": {f: round(v) for f, v in fields.items()}, "ctc": round(ctc) if ctc else None, "unmatched": unmatched[:10]}
