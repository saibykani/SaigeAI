"""Offer calculator tests. Expected values are hand-computed from the FY 2025-26 slabs (see comments)."""

from app.database import collections as c
from app.offers.engine import auto_split, buyout, calculate, compare, hra_exemption, tax_on
from app.offers.models import CompareRequest, OfferInput, SplitRequest
from app.offers.parse import parse_breakup


def offer_for(ctc: float, **kw) -> OfferInput:
    s = auto_split(SplitRequest(ctc=ctc, **{k: v for k, v in kw.items() if k in ("variable_pct",)}))
    rest = {k: v for k, v in kw.items() if k != "variable_pct"}
    return OfferInput(**{k: v for k, v in s.items()}, **rest)


# ---- tax function ---------------------------------------------------------------------------------------------------


def test_new_regime_slabs_and_rebate():
    assert tax_on(1_200_000, "new")["total_tax"] == 0  # 87A rebate
    assert tax_on(400_000, "new")["total_tax"] == 0
    # 12.1L: slabs 20,000 + 40,000 + 1,500 = 61,500, but marginal relief caps at 10,000 (the excess over 12L); cess 400
    assert tax_on(1_210_000, "new") == {"slab_tax": 61_500, "tax_after_rebate": 10_000, "surcharge": 0, "cess": 400, "total_tax": 10_400}
    assert tax_on(1_250_000, "new")["total_tax"] == 52_000  # relief: 50,000 + 4% cess
    assert tax_on(1_300_000, "new")["total_tax"] == 78_000  # no relief: 75,000 + 3,000
    assert tax_on(2_500_000, "new")["slab_tax"] == 20_000 + 40_000 + 60_000 + 80_000 + 100_000 + 30_000  # 3,30,000


def test_old_regime_slabs_and_rebate():
    assert tax_on(500_000, "old")["total_tax"] == 0  # rebate up to 5L
    assert tax_on(600_000, "old")["total_tax"] == 33_800  # 12,500 + 20,000 = 32,500, cess 1,300
    assert tax_on(1_200_000, "old")["slab_tax"] == 12_500 + 100_000 + 60_000


def test_surcharge_and_marginal_relief():
    t = tax_on(5_521_560, "new")  # slab 3,00,000 + 30% x 31,21,560 = 12,36,468 + 10% surcharge, below relief cap
    assert (t["slab_tax"], t["surcharge"], t["cess"], t["total_tax"]) == (1_236_468, 123_647, 54_405, 1_414_520)
    r = tax_on(5_010_000, "new")  # at 50L tax is 10,80,000; surcharge relief caps the total at 10,80,000 + 10,000
    assert r["tax_after_rebate"] + r["surcharge"] == 1_090_000


# ---- HRA ------------------------------------------------------------------------------------------------------------


def test_hra_exemption_rules():
    base = dict(basic=600_000, hra=240_000)
    assert hra_exemption(OfferInput(**base, rent_paid=300_000, city="metro")) == 240_000  # min(2.4L, 3L-60k, 3L)
    assert hra_exemption(OfferInput(**base, rent_paid=200_000, city="non_metro")) == 140_000  # min(2.4L, 2L-60k, 2.4L)
    assert hra_exemption(OfferInput(**base, rent_paid=50_000)) == 0  # rent below 10% of basic
    assert hra_exemption(OfferInput(**base, rent_paid=0)) == 0


# ---- full salaries (auto-split structure, Karnataka PT 2,400, no deductions) -----------------------------------------


def test_split_structure_is_exact():
    s = auto_split(SplitRequest(ctc=1_275_000))
    assert s["basic"] == 510_000 and s["hra"] == 255_000 and s["employer_pf"] == 61_200 and s["gratuity"] == 24_531 and s["special"] == 424_269
    assert calculate(offer_for(1_275_000))["ctc"] == 1_275_000


def test_8l_ctc():
    # basic 3.2L hra 1.6L pf 38,400 gratuity 15,392 special 2,66,208 -> gross 7,46,208
    r = calculate(offer_for(800_000))
    assert r["ctc"] == 800_000
    new, old = r["regimes"]["new"], r["regimes"]["old"]
    assert new["gross"] == 746_208 and new["taxable_income"] == 671_208 and new["total_tax"] == 0
    assert new["annual_in_hand"] == 746_208 - 38_400 - 2_400 == 705_408
    # old: 7,46,208 - 50,000 - 2,400 (PT) - 38,400 (80C via PF) = 6,55,408 -> 12,500 + 20% x 1,55,408 = 43,582 + cess 1,743
    assert old["taxable_income"] == 655_408 and old["total_tax"] == 45_325
    assert old["annual_in_hand"] == 660_083
    assert r["best_regime"] == "new" and r["regime_saving"] == 705_408 - 660_083
    assert r["real_monthly_cash"] == 58_784  # 705,408 / 12 = 58,784


def test_12_75l_ctc_zero_tax_new_regime():
    r = calculate(offer_for(1_275_000))
    new = r["regimes"]["new"]
    assert new["gross"] == 1_189_269 and new["taxable_income"] == 1_114_269 and new["total_tax"] == 0
    assert new["annual_in_hand"] == 1_189_269 - 61_200 - 2_400 == 1_125_669
    assert r["monthly_in_hand"] == 93_806


def test_18l_ctc():
    # gross 16,78,968; new taxable 16,03,968: 20k + 40k + 60k + 20% x 3,968 (794) = 1,20,794 + cess 4,832 = 1,25,626
    r = calculate(offer_for(1_800_000))
    new, old = r["regimes"]["new"], r["regimes"]["old"]
    assert new["gross"] == 1_678_968 and new["taxable_income"] == 1_603_968 and new["total_tax"] == 125_626
    assert new["annual_in_hand"] == 1_678_968 - 86_400 - 2_400 - 125_626 == 1_464_542
    # old: 16,78,968 - 50,000 - 2,400 - 86,400 = 15,40,168 -> 12,500 + 1,00,000 + 30% x 5,40,168 = 2,74,550 + cess 10,982
    assert old["taxable_income"] == 1_540_168 and old["total_tax"] == 285_532
    assert r["best_regime"] == "new" and r["regime_saving"] == 285_532 - 125_626


def test_35l_ctc():
    # gross 32,64,660; new taxable 31,89,660: 3,00,000 + 30% x 7,89,660 = 5,36,898 + cess 21,476 = 5,58,374
    r = calculate(offer_for(3_500_000))
    new, old = r["regimes"]["new"], r["regimes"]["old"]
    assert new["gross"] == 3_264_660 and new["total_tax"] == 558_374
    assert new["annual_in_hand"] == 3_264_660 - 168_000 - 2_400 - 558_374 == 2_535_886
    # old: 32,64,660 - 50,000 - 2,400 - 1,50,000 (80C cap) = 30,62,260 -> 12,500 + 1,00,000 + 30% x 20,62,260 = 7,31,178 + cess 29,247
    assert old["taxable_income"] == 3_062_260 and old["total_tax"] == 760_425


def test_60l_ctc_with_surcharge():
    # gross 55,96,560; new taxable 55,21,560: 12,36,468 + 10% surcharge 1,23,647 + cess 54,405 = 14,14,520
    r = calculate(offer_for(6_000_000))
    new = r["regimes"]["new"]
    assert new["taxable_income"] == 5_521_560 and new["surcharge"] == 123_647 and new["total_tax"] == 1_414_520
    assert new["annual_in_hand"] == 5_596_560 - 288_000 - 2_400 - 1_414_520 == 3_891_640


def test_old_regime_wins_with_rent_and_deductions():
    # 18L: HRA 3.6L fully exempt with 4.8L rent (metro, 50% of basic = 3.6L), 80C 1.5L, 80D 25k, NPS 50k, home loan 2L
    r = calculate(offer_for(1_800_000, rent_paid=480_000, sec80c=100_000, sec80d=25_000, employee_nps=50_000, home_loan_interest=200_000))
    old = r["regimes"]["old"]
    assert old["exemptions"]["hra"] == 360_000 and old["deductions"]["sec80c"] == 150_000
    # 16,78,968 - 3,60,000 - 50,000 - 2,400 - 1,50,000 - 25,000 - 50,000 - 2,00,000 = 8,41,568 -> 12,500 + 20% x 3,41,568 = 80,814 + cess 3,233
    assert old["taxable_income"] == 841_568 and old["total_tax"] == 84_047
    assert r["best_regime"] == "old" and r["regime_saving"] == (1_678_968 - 86_400 - 2_400 - 84_047) - 1_464_542


def test_variable_joining_esop_and_first_year():
    o = OfferInput(basic=600_000, hra=300_000, special=300_000, variable=200_000, variable_payout_pct=50, joining_bonus=100_000, esop_annual=150_000)
    r = calculate(o)
    assert r["variable_expected"] == 100_000
    assert r["ctc"] == 600_000 + 300_000 + 300_000 + 72_000 + 200_000  # employer PF defaults to 12% of basic
    assert r["total_first_year_value"] == r["ctc"] - 200_000 + 100_000 + 100_000 + 150_000
    new = r["regimes"]["new"]
    assert new["gross"] == 1_300_000  # fixed cash 12L + 1L expected variable
    assert new["fixed_annual_in_hand"] == 1_200_000 - 72_000 - 2_400  # 12L - 75k std = 11.25L taxable -> rebate -> 0 tax
    assert r["real_monthly_cash"] == round((1_200_000 - 72_000 - 2_400) / 12)
    assert new["first_year_in_hand"] < new["annual_in_hand"] + 100_000  # joining bonus is taxed
    assert sum(w["value"] for w in r["waterfall"][:-1]) == r["annual_in_hand"]


def test_pf_capped_and_pt_override():
    capped = calculate(OfferInput(basic=600_000, hra=0, special=600_000, pf_mode="capped", pt_annual=0))
    assert capped["regimes"]["new"]["employee_pf"] == 21_600
    assert capped["regimes"]["new"]["professional_tax"] == 0
    assert calculate(OfferInput(basic=100_000, state="MH"))["regimes"]["new"]["professional_tax"] == 2_500
    assert calculate(OfferInput(basic=100_000, state="DL"))["regimes"]["new"]["professional_tax"] == 0


# ---- compare, hike, buyout ------------------------------------------------------------------------------------------


def test_compare_hike_buyout_breakeven():
    cur = offer_for(1_000_000, name="Current")
    a, b = offer_for(1_500_000, name="A"), offer_for(1_800_000, name="B")
    out = compare(CompareRequest(offers=[a, b], current=cur, notice_days=60, buyout_basis="basic"))
    assert out["winner"] == 1
    row = out["offers"][0]
    assert row["hike_ctc_pct"] == 50.0
    assert row["hike_in_hand_pct"] > 0
    assert row["monthly_in_hand_gain"] == row["result"]["monthly_in_hand"] - out["current"]["monthly_in_hand"]
    assert row["buyout"]["cost"] == round(400_000 / 365 * 60) and row["buyout"]["per_day"] == 1_096
    assert row["break_even_months"] == round(row["buyout"]["cost"] / row["real_monthly_cash_gain"], 1)
    assert compare(CompareRequest(offers=[a]))["winner"] is None


def test_buyout_gross_basis():
    o = OfferInput(basic=600_000, hra=240_000, special=160_000)
    assert buyout(o, 30, "gross")["cost"] == round(1_000_000 / 365 * 30)
    assert buyout(OfferInput(basic=365_000), 60, "basic")["cost"] == 60_000


# ---- parser ---------------------------------------------------------------------------------------------------------


def test_parse_breakup_text():
    txt = """Total CTC: 18 LPA
Basic Salary  6,00,000
HRA 2,40,000
Special Allowance | 50,000 per month
Employer PF Contribution 72,000
Gratuity 28,860
Variable Pay (target) Rs. 1,80,000
Joining Bonus 2 lakh
Health Insurance 15,000
Employee PF 72,000
Something weird 12"""
    p = parse_breakup(txt)
    f = p["fields"]
    assert p["ctc"] == 1_800_000
    assert f["basic"] == 600_000 and f["hra"] == 240_000 and f["special"] == 600_000
    assert f["employer_pf"] == 72_000 and f["gratuity"] == 28_860 and f["variable"] == 180_000
    assert f["joining_bonus"] == 200_000 and f["insurance"] == 15_000
    assert "Something weird 12" in p["unmatched"]


# ---- API ------------------------------------------------------------------------------------------------------------


async def test_offers_api_and_saved_offers(client, auth, db):
    assert (await client.post("/api/offers/calculate", json={})).status_code == 401
    r = await client.post("/api/offers/calculate", headers=auth, json={"basic": 600_000, "hra": 300_000, "special": 300_000})
    assert r.status_code == 200 and r.json()["best_regime"] == "new"
    sp = (await client.post("/api/offers/split", headers=auth, json={"ctc": 1_800_000, "variable_pct": 10})).json()
    assert sp["variable"] == 180_000 and sp["basic"] == 648_000
    cmp = await client.post("/api/offers/compare", headers=auth, json={"offers": [sp | {"name": "X"}], "current": {"basic": 400_000}})
    assert cmp.status_code == 200
    assert (await client.post("/api/offers/compare", headers=auth, json={"offers": []})).status_code == 422
    assert (await client.post("/api/offers/parse", headers=auth, json={"text": "Basic 6,00,000"})).json()["fields"]["basic"] == 600_000
    assert (await client.get("/api/offers/rules", headers=auth)).json()["states"]["KA"] == "Karnataka"

    s = await client.post("/api/offers/saved", headers=auth, json={"input": {"name": "Acme", "basic": 600_000, "hra": 300_000}})
    assert s.status_code == 201
    oid = s.json()["id"]
    lst = (await client.get("/api/offers/saved", headers=auth)).json()
    assert len(lst) == 1 and lst[0]["input"]["name"] == "Acme"
    up = await client.put(f"/api/offers/saved/{oid}", headers=auth, json={"input": {"name": "Acme 2", "basic": 700_000}})
    assert up.status_code == 200
    assert (await client.get("/api/offers/saved", headers=auth)).json()[0]["input"]["name"] == "Acme 2"
    assert await db[c.AUDIT_LOGS].count_documents({"action": {"$in": ["offer.saved", "offer.updated"]}}) == 2
    assert (await client.delete(f"/api/offers/saved/{oid}", headers=auth)).status_code == 200
    assert (await client.delete(f"/api/offers/saved/{oid}", headers=auth)).status_code == 404
    assert c.SAVED_OFFERS in c.USER_SCOPED
