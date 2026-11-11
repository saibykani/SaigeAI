"""Job category (manual testing, automation testing, QA, other) and compensation read from the posting itself.

Nothing is guessed: compensation is filled only when the posting states a figure, and `salary_lpa` is that
figure converted to INR lakhs per annum (fixed reference rates) so postings in different currencies can be
filtered together. The original text is kept in `salary_text`.
"""

import re

CATEGORIES = {"manual": "Manual testing", "automation": "Automation testing", "qa": "QA (general)", "other": "Other roles"}

_QA_TITLE = re.compile(r"\b(qa|qe|sdet\d?|test(er|ing)?|quality assurance|quality engineer|uat)\b", re.I)
_AUTO_TITLE = re.compile(r"\b(automation|sdet\d?|selenium|playwright|cypress|appium|test automation|framework)\b", re.I)
_MANUAL_TITLE = re.compile(r"\b(manual|functional test|uat|qa analyst|test analyst|qa executive|software tester|game tester|qa tester)\b", re.I)
_MANUAL_BODY = re.compile(r"\bmanual (testing|test|qa)\b|\btest case (design|execution)\b|\bexploratory testing\b|\bregression testing\b", re.I)
_AUTO_BODY = re.compile(r"\b(selenium|playwright|cypress|appium|webdriverio|rest ?assured|testng|pytest|junit)\b", re.I)


def category(title: str, description: str = "") -> str:
    t, d = title or "", (description or "")[:6000]
    if not _QA_TITLE.search(t):
        return "other"
    if _MANUAL_TITLE.search(t):
        return "manual"
    if _AUTO_TITLE.search(t):
        return "automation"
    manual, auto = len(_MANUAL_BODY.findall(d)), len(_AUTO_BODY.findall(d))
    if manual and manual >= auto:
        return "manual"
    if auto:
        return "automation"
    return "qa"


# ------------------------------------------------------------------ compensation

TO_INR = {"INR": 1.0, "USD": 84.0, "EUR": 90.0, "GBP": 106.0, "CAD": 61.0, "AUD": 55.0, "SGD": 62.0, "AED": 22.9}
_SYM = {"₹": "INR", "rs": "INR", "inr": "INR", "$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR", "£": "GBP", "gbp": "GBP",
        "cad": "CAD", "aud": "AUD", "sgd": "SGD", "aed": "AED"}
_NUM = r"(\d{1,3}(?:[,.]\d{3})+|\d+(?:\.\d+)?)\s*(k|K|lpa|LPA|lakhs?|Lakhs?|L|cr|crore)?"
_LPA = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?)?\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*(lpa|lakhs?|l\b)", re.I)
_LPA1 = re.compile(r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)\s*(lpa|lakhs?)", re.I)
_RANGE = re.compile(r"(₹|\$|€|£|\b(?:usd|eur|gbp|cad|aud|sgd|aed|inr|rs)\b)\s?" + _NUM + r"\s*(?:-|–|to)\s*(?:₹|\$|€|£)?\s?" + _NUM, re.I)


def _val(num: str, unit: str | None) -> float:
    # "120,000" and "120.000" are thousands; "7.5" is a decimal.
    n = float(re.sub(r"[,.](?=\d{3}\b)", "", num).replace(",", ""))
    u = (unit or "").lower()
    if u == "k":
        n *= 1_000
    elif u in ("lpa", "lakh", "lakhs", "l"):
        n *= 100_000
    elif u in ("cr", "crore"):
        n *= 10_000_000
    return n


def compensation(text: str, ashby_summary: str | None = None) -> dict:
    """{salary_min, salary_max, salary_currency, salary_lpa, salary_text} or {} when the posting states no pay."""
    src = " ".join(x for x in (ashby_summary, (text or "")[:20000]) if x)
    if not src:
        return {}
    m = _LPA.search(src)
    if m:
        lo, hi = float(m.group(1)) * 100_000, float(m.group(2)) * 100_000
        return _out(lo, hi, "INR", m.group(0))
    m = _LPA1.search(src)
    if m:
        v = float(m.group(1)) * 100_000
        return _out(v, v, "INR", m.group(0))
    for m in _RANGE.finditer(src):
        cur = _SYM.get(m.group(1).lower().rstrip("."), "USD")
        try:
            lo, hi = _val(m.group(2), m.group(3)), _val(m.group(4), m.group(5) or m.group(3))
        except ValueError:
            continue
        window = src[m.end():m.end() + 25].lower()
        if "hour" in window or "/hr" in window:
            lo, hi = lo * 2080, hi * 2080
        elif "month" in window:
            lo, hi = lo * 12, hi * 12
        if hi < lo or lo < 1000:  # not a salary (e.g. "$5 - 10 million funding")
            continue
        return _out(lo, hi, cur, m.group(0))
    return {}


def _out(lo: float, hi: float, cur: str, raw: str) -> dict:
    inr = TO_INR.get(cur, 84.0)
    return {"salary_min": round(lo), "salary_max": round(hi), "salary_currency": cur,
            "salary_lpa": round(lo * inr / 100_000, 1), "salary_text": re.sub(r"\s+", " ", raw).strip()[:60]}
