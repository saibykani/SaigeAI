"""Offer decision layer: money over 4 years (reusing engine.calculate), commute time and a weighted 0-100 score. Pure, no I/O."""

from typing import Any

from app.offers.engine import calculate, rnd
from app.offers.models import OfferInput, OfferMeta

FACTORS = ["money", "growth", "work_life", "commute", "learning", "user_set"]
DEFAULT_WEIGHTS = {"money": 40.0, "growth": 20.0, "work_life": 15.0, "commute": 10.0, "learning": 10.0, "user_set": 5.0}
WEEKS_PER_MONTH = 52 / 12
COMMUTE_BAD_HOURS = 60.0  # a commute at or above this many hours a month scores 0
NEUTRAL = 50.0  # used when you have not rated a factor; listed under "unrated" so it is never hidden
YEARS = 4


def normalise(w: dict[str, float]) -> dict[str, float]:
    total = sum(w.values())
    if total <= 0:
        return {f: round(100 / len(FACTORS), 2) for f in FACTORS}
    return {f: round(w[f] / total * 100, 2) for f in FACTORS}


def parse_weights(raw: str) -> dict[str, float]:
    """Text like money:40,growth:20 becomes normalised percentages. Missing factors get 0; invalid parts are ignored; none given means defaults."""
    w: dict[str, float] = {}
    for part in raw.split(","):
        name, _, val = part.partition(":")
        try:
            v = float(val)
        except ValueError:
            continue
        if name.strip() in FACTORS and 0 <= v <= 1000:
            w[name.strip()] = v
    return normalise({f: w.get(f, 0.0) for f in FACTORS} if w else DEFAULT_WEIGHTS)


def esop_vested(meta: OfferMeta, esop_annual: float, months: int) -> int:
    """Value vested after `months` at the user-entered value. A total grant follows cliff + linear vesting; otherwise the entered per-year value."""
    if meta.esop_grant_value > 0:
        if months < meta.esop_cliff_months:
            return 0
        return rnd(meta.esop_grant_value * min(1.0, months / (meta.esop_vesting_years * 12)))
    return rnd(esop_annual * months / 12)


def commute_hours(meta: OfferMeta) -> float:
    office_days = max(0, 5 - meta.wfh_days) * WEEKS_PER_MONTH
    return round(meta.commute_minutes * 2 * office_days / 60, 1)


def offer_numbers(inp: OfferInput, meta: OfferMeta) -> dict[str, Any]:
    r = calculate(inp)
    y1_cash = r["first_year_in_hand"]  # after tax; includes joining bonus and expected variable
    cash_4y = y1_cash + (YEARS - 1) * r["annual_in_hand"]
    esop_1, esop_4 = esop_vested(meta, inp.esop_annual, 12), esop_vested(meta, inp.esop_annual, YEARS * 12)
    return {
        "name": inp.name, "company": inp.company, "ctc": r["ctc"], "best_regime": r["best_regime"],
        "monthly_in_hand": r["monthly_in_hand"], "real_monthly_cash": r["real_monthly_cash"],
        "year1_cash": y1_cash, "year1_esop": esop_1, "year1_total": y1_cash + esop_1,
        "cash_4y": cash_4y, "esop_4y": esop_4, "total_4y": cash_4y + esop_4,
        "commute_hours_month": commute_hours(meta), "wfh_days": meta.wfh_days, "commute_minutes": meta.commute_minutes,
        "location": meta.location, "notice_days": meta.notice_days, "buyout_amount": rnd(meta.buyout_amount),
        "benefits": meta.benefits, "health_cover": rnd(meta.health_cover), "learning_budget": rnd(meta.learning_budget),
        "growth_notes": meta.growth_notes, "application_id": meta.application_id,
    }


def _rated(v: int | None) -> tuple[float, bool]:
    return (v * 10.0, False) if v is not None else (NEUTRAL, True)


def factor_scores(nums: list[dict[str, Any]], metas: list[OfferMeta]) -> list[dict[str, tuple[float, bool]]]:
    """Each factor 0-100, with a flag when it was unrated (neutral). Money and learning budget are relative to the best offer."""
    best = max((n["total_4y"] for n in nums), default=0)
    top_budget = max((n["learning_budget"] for n in nums), default=0)
    out = []
    for n, m in zip(nums, metas, strict=True):
        if m.learning_rating is not None:
            learning = (m.learning_rating * 10.0, False)
        elif top_budget > 0:
            learning = (n["learning_budget"] / top_budget * 100, False)
        else:
            learning = (NEUTRAL, True)
        out.append({
            "money": (n["total_4y"] / best * 100 if best > 0 else 0.0, False),
            "growth": _rated(m.growth_rating),
            "work_life": (m.wfh_days / 5 * 100, False),
            "commute": (max(0.0, 100 - n["commute_hours_month"] / COMMUTE_BAD_HOURS * 100), False),
            "learning": learning,
            "user_set": _rated(m.user_rating),
        })
    return out


def compare_saved(rows: list[dict[str, Any]], weights: dict[str, float]) -> dict[str, Any]:
    metas = [OfferMeta(**(r.get("meta") or {})) for r in rows]
    nums = [{"id": r["_id"], **offer_numbers(OfferInput(**r["input"]), m)} for r, m in zip(rows, metas, strict=True)]
    for n, sc in zip(nums, factor_scores(nums, metas), strict=True):
        breakdown = {
            f: {"score": round(sc[f][0], 1), "weight_pct": weights[f], "contribution": round(sc[f][0] * weights[f] / 100, 1)} for f in FACTORS
        }
        n["breakdown"] = breakdown
        n["unrated"] = [f for f in FACTORS if sc[f][1] and weights[f] > 0]
        n["score"] = round(sum(b["contribution"] for b in breakdown.values()), 1)
    winner = max(range(len(nums)), key=lambda i: nums[i]["score"]) if len(nums) > 1 else None
    return {"offers": nums, "weights": weights, "winner": winner, "factors": FACTORS, "years": YEARS,
            "esop_note": "ESOP is counted before tax at the value you entered. It is not cash until you sell."}
