"""Pure in-hand salary engine for India. No I/O: everything comes from the inputs and offers/constants.py."""

from typing import Any

from app.offers import constants as k
from app.offers.models import CompareRequest, OfferInput, SplitRequest


def rnd(x: float) -> int:
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def slab_tax(taxable: float, slabs: list[tuple[float | None, float]]) -> float:
    tax, lower = 0.0, 0.0
    for upper, rate in slabs:
        if taxable <= lower:
            break
        top = taxable if upper is None else min(taxable, upper)
        tax += (top - lower) * rate
        lower = upper if upper is not None else lower
    return tax


def tax_on(taxable: float, regime: str) -> dict[str, int]:
    """Tax for a taxable income: slabs, 87A rebate (+ marginal relief), surcharge (+ marginal relief), 4% cess."""
    new = regime == "new"
    slabs = k.NEW_SLABS if new else k.OLD_SLABS
    base = slab_tax(taxable, slabs)
    limit = k.NEW_REBATE_LIMIT if new else k.OLD_REBATE_LIMIT
    if taxable <= limit:
        base_after = 0.0
    elif new:
        base_after = min(base, taxable - limit)  # marginal relief: never pay more than the income above the rebate limit
    else:
        base_after = base
    surcharge = 0.0
    table = k.SURCHARGE_NEW if new else k.SURCHARGE_OLD
    applicable = [(t, r) for t, r in table if taxable > t]
    if applicable and base_after > 0:
        thr, rate = applicable[-1]
        prev = next((r for t, r in reversed(table) if t < thr), 0.0)
        at_thr = min(slab_tax(thr, slabs), max(0.0, thr - limit)) if new else slab_tax(thr, slabs)
        total = min(base_after * (1 + rate), at_thr * (1 + prev) + (taxable - thr))
        surcharge = max(0.0, total - base_after)
    pre_cess = rnd(base_after + surcharge)
    cess = rnd(pre_cess * k.CESS_RATE)
    return {"slab_tax": rnd(base), "tax_after_rebate": rnd(base_after), "surcharge": rnd(surcharge), "cess": cess, "total_tax": pre_cess + cess}


def employee_pf(o: OfferInput) -> int:
    wages = min(o.basic, k.PF_WAGE_CEILING) if o.pf_mode == "capped" else o.basic
    return rnd(wages * k.PF_RATE)


def professional_tax(o: OfferInput) -> int:
    if o.pt_annual is not None:
        return rnd(o.pt_annual)
    return rnd(k.PROFESSIONAL_TAX.get(o.state.upper(), 0))


def hra_exemption(o: OfferInput) -> int:
    if o.rent_paid <= 0 or o.hra <= 0:
        return 0
    pct = k.HRA_METRO_PCT if o.city == "metro" else k.HRA_NON_METRO_PCT
    return rnd(max(0.0, min(o.hra, o.rent_paid - 0.10 * o.basic, pct * o.basic)))


def _regime(o: OfferInput, regime: str, variable: float, joining: float) -> dict[str, Any]:
    gross = o.basic + o.hra + o.special + o.lta + o.other_allowances + variable + joining
    epf, pt = employee_pf(o), professional_tax(o)
    new = regime == "new"
    ex: dict[str, int] = {}
    ded: dict[str, int] = {}
    if new:
        std = k.NEW_STANDARD_DEDUCTION
        ded["employer_nps"] = rnd(min(o.employer_nps, k.EMPLOYER_NPS_CAP_NEW * o.basic))
    else:
        std = k.OLD_STANDARD_DEDUCTION
        ex["hra"] = hra_exemption(o)
        ex["lta"] = rnd(min(o.lta_claimed, o.lta))
        ded["professional_tax"] = pt
        ded["employer_nps"] = rnd(min(o.employer_nps, k.EMPLOYER_NPS_CAP_OLD * o.basic))
        ded["sec80c"] = rnd(min(k.CAP_80C, epf + o.sec80c))
        ded["sec80d"] = rnd(min(k.CAP_80D, o.sec80d))
        ded["nps_80ccd1b"] = rnd(min(k.CAP_80CCD_1B, o.employee_nps))
        ded["home_loan_interest"] = rnd(min(k.CAP_HOME_LOAN_INTEREST, o.home_loan_interest))
    taxable = max(0, rnd(gross) - sum(ex.values()) - std - sum(ded.values()))
    t = tax_on(taxable, regime)
    in_hand = rnd(gross) - epf - pt - t["total_tax"]
    return {
        "regime": regime, "gross": rnd(gross), "exemptions": ex, "standard_deduction": std, "deductions": ded,
        "taxable_income": taxable, **t, "employee_pf": epf, "professional_tax": pt, "annual_in_hand": in_hand,
        "effective_rate": round(t["total_tax"] / gross * 100, 2) if gross else 0.0,
    }


def calculate(o: OfferInput) -> dict[str, Any]:
    recv = o.variable * o.variable_payout_pct / 100
    epf_employer = o.employer_pf if o.employer_pf is not None else employee_pf(o)
    fixed = o.basic + o.hra + o.special + o.lta + o.other_allowances + epf_employer + o.gratuity + o.insurance + o.employer_nps
    ctc = fixed + o.variable
    non_cash = epf_employer + o.gratuity + o.insurance + o.employer_nps
    regimes: dict[str, Any] = {}
    for reg in ("new", "old"):
        r = _regime(o, reg, recv, 0)
        fx = _regime(o, reg, 0, 0)
        fy = _regime(o, reg, recv, o.joining_bonus)
        r["fixed_annual_in_hand"] = fx["annual_in_hand"]
        r["real_monthly_cash"] = round(fx["annual_in_hand"] / 12)
        r["monthly_in_hand"] = round(r["annual_in_hand"] / 12)
        r["first_year_in_hand"] = fy["annual_in_hand"]
        r["first_year_tax"] = fy["total_tax"]
        regimes[reg] = r
    best = "new" if regimes["new"]["annual_in_hand"] >= regimes["old"]["annual_in_hand"] else "old"
    other = "old" if best == "new" else "new"
    b = regimes[best]
    return {
        "name": o.name, "company": o.company, "fy": k.FY_LABEL,
        "ctc": rnd(ctc), "fixed_ctc": rnd(fixed), "variable_target": rnd(o.variable), "variable_expected": rnd(recv),
        "fixed_pct": round(fixed / ctc * 100, 1) if ctc else 0.0, "variable_pct": round(o.variable / ctc * 100, 1) if ctc else 0.0,
        "joining_bonus": rnd(o.joining_bonus), "esop_annual": rnd(o.esop_annual),
        "total_first_year_value": rnd(ctc - o.variable + recv + o.joining_bonus + o.esop_annual),
        "regimes": regimes, "best_regime": best, "regime_saving": regimes[best]["annual_in_hand"] - regimes[other]["annual_in_hand"],
        "real_monthly_cash": b["real_monthly_cash"], "monthly_in_hand": b["monthly_in_hand"], "annual_in_hand": b["annual_in_hand"],
        "first_year_in_hand": b["first_year_in_hand"], "in_hand_pct_of_ctc": round(b["annual_in_hand"] / ctc * 100, 1) if ctc else 0.0,
        "waterfall": [
            {"key": "ctc", "label": "CTC", "value": rnd(ctc)},
            {"key": "employer_only", "label": "Employer PF, gratuity, insurance, NPS", "value": -rnd(non_cash)},
            {"key": "variable_unpaid", "label": "Variable not paid out", "value": -rnd(o.variable - recv)},
            {"key": "employee_pf", "label": "Your PF (savings)", "value": -b["employee_pf"]},
            {"key": "pt", "label": "Professional tax", "value": -b["professional_tax"]},
            {"key": "tax", "label": "Income tax and cess", "value": -b["total_tax"]},
            {"key": "in_hand", "label": "In-hand", "value": b["annual_in_hand"]},
        ],
        "assumptions": k.ASSUMPTIONS,
    }


def auto_split(s: SplitRequest) -> dict[str, float | str]:
    """Typical structure for a CTC: basic 40%, HRA 50% of basic, employer PF 12%, gratuity 4.81%, the rest special allowance."""
    variable = round(s.ctc * s.variable_pct / 100)
    fixed = s.ctc - variable
    basic = round(fixed * s.basic_pct / 100)
    hra = round(basic * s.hra_pct_of_basic / 100)
    pf = round(min(basic, k.PF_WAGE_CEILING) * k.PF_RATE) if s.pf_mode == "capped" else round(basic * k.PF_RATE)
    gratuity = round(basic * k.GRATUITY_PCT_OF_BASIC)
    special = max(0, round(fixed - basic - hra - pf - gratuity - s.insurance))
    return {"basic": basic, "hra": hra, "special": special, "employer_pf": pf, "gratuity": gratuity, "insurance": s.insurance,
            "variable": variable, "pf_mode": s.pf_mode}


def buyout(o: OfferInput, days: int, basis: str) -> dict[str, Any]:
    base = o.basic if basis == "basic" else o.basic + o.hra + o.special + o.lta + o.other_allowances
    per_day = base / 365
    return {"days": days, "basis": basis, "per_day": rnd(per_day), "cost": rnd(per_day * days)}


def compare(req: CompareRequest) -> dict[str, Any]:
    """Offers side by side; hike and buyout figures use the CURRENT salary's pay for the buyout and the new offer's in-hand gain."""
    results = [calculate(o) for o in req.offers]
    cur = calculate(req.current) if req.current else None
    # The notice period is served at the current employer, so the buyout is priced on the current salary.
    bo = buyout(req.current, req.notice_days, req.buyout_basis) if req.current and req.notice_days else None
    out_offers = []
    for r in results:
        row: dict[str, Any] = {"result": r, "buyout": bo}
        if cur:
            cm, nm = cur["monthly_in_hand"], r["monthly_in_hand"]
            row["hike_ctc_pct"] = round((r["ctc"] - cur["ctc"]) / cur["ctc"] * 100, 1) if cur["ctc"] else None
            row["hike_in_hand_pct"] = round((nm - cm) / cm * 100, 1) if cm else None
            row["monthly_in_hand_gain"] = nm - cm
            gain = r["real_monthly_cash"] - cur["real_monthly_cash"]
            row["real_monthly_cash_gain"] = gain
            row["break_even_months"] = round(bo["cost"] / gain, 1) if bo and gain > 0 else None
        out_offers.append(row)
    winner = max(range(len(results)), key=lambda i: results[i]["annual_in_hand"])
    return {"offers": out_offers, "current": cur, "winner": winner if len(results) > 1 else None, "fy": k.FY_LABEL}
