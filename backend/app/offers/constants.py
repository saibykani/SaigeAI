"""Published Indian income-tax rules used by the offer calculator. Update this one file when a new Finance Act changes them."""

FY_LABEL = "FY 2025-26 (AY 2026-27)"

# (upper bound of the slab, rate). The last slab has no upper bound.
NEW_SLABS: list[tuple[float | None, float]] = [
    (400_000, 0.0), (800_000, 0.05), (1_200_000, 0.10), (1_600_000, 0.15), (2_000_000, 0.20), (2_400_000, 0.25), (None, 0.30),
]
OLD_SLABS: list[tuple[float | None, float]] = [(250_000, 0.0), (500_000, 0.05), (1_000_000, 0.20), (None, 0.30)]

NEW_STANDARD_DEDUCTION = 75_000
OLD_STANDARD_DEDUCTION = 50_000
NEW_REBATE_LIMIT = 1_200_000  # section 87A: no tax up to this taxable income, with marginal relief just above it
OLD_REBATE_LIMIT = 500_000
CESS_RATE = 0.04

# (income threshold, surcharge rate). New regime surcharge is capped at 25%, old regime goes to 37%.
SURCHARGE_NEW: list[tuple[float, float]] = [(5_000_000, 0.10), (10_000_000, 0.15), (20_000_000, 0.25)]
SURCHARGE_OLD: list[tuple[float, float]] = [(5_000_000, 0.10), (10_000_000, 0.15), (20_000_000, 0.25), (50_000_000, 0.37)]

CAP_80C = 150_000
CAP_80CCD_1B = 50_000
CAP_80D = 100_000  # self + parents (senior citizens); the user enters the eligible amount
CAP_HOME_LOAN_INTEREST = 200_000  # section 24(b), self-occupied
EMPLOYER_NPS_CAP_NEW = 0.14  # of basic, section 80CCD(2)
EMPLOYER_NPS_CAP_OLD = 0.10
HRA_METRO_PCT = 0.50
HRA_NON_METRO_PCT = 0.40
PF_WAGE_CEILING = 15_000 * 12  # statutory EPF wage ceiling per year when "capped" is chosen
PF_RATE = 0.12
GRATUITY_PCT_OF_BASIC = 0.0481  # 15/26 x 1/12, used only by the auto-split helper

# Professional tax per year by state (typical salaried slab above the top threshold). Configurable per offer.
PROFESSIONAL_TAX: dict[str, float] = {
    "KA": 2400, "TG": 2400, "MH": 2500, "TN": 2500, "AP": 2400, "WB": 2400, "GJ": 2400, "KL": 2500, "MP": 2500,
    "DL": 0, "HR": 0, "UP": 0, "RJ": 0, "PB": 0, "OTHER": 0,
}
STATE_NAMES: dict[str, str] = {
    "KA": "Karnataka", "TG": "Telangana", "MH": "Maharashtra", "TN": "Tamil Nadu", "AP": "Andhra Pradesh", "WB": "West Bengal",
    "GJ": "Gujarat", "KL": "Kerala", "MP": "Madhya Pradesh", "DL": "Delhi", "HR": "Haryana", "UP": "Uttar Pradesh",
    "RJ": "Rajasthan", "PB": "Punjab", "OTHER": "Other (no professional tax)",
}

ASSUMPTIONS = [
    "Tax rules are the published slabs for " + FY_LABEL + "; salary is assumed to be earned for the full year.",
    "Employer PF, gratuity, insurance and employer NPS are part of CTC but never reach your bank account.",
    "Employee PF is 12% of basic (or of the Rs 15,000/month wage ceiling if capped). It is deducted from pay "
    "and counts under 80C in the old regime.",
    "Employer NPS (80CCD(2)) is deductible up to 14% of basic in the new regime and 10% in the old regime.",
    "HRA exemption (old regime only) is the least of actual HRA, rent paid minus 10% of basic, and 50% (metro) or 40% (non-metro) of basic. "
    "DA is taken as zero.",
    "LTA is taxable unless you enter the amount you actually claim with travel bills. Professional tax is deductible in the old regime only.",
    "Variable pay is counted at the expected payout %. 80C, 80D, NPS and home-loan interest are your own spends: "
    "they cut tax but are not deducted from in-hand.",
    "ESOP/RSU value is shown as paper value only and is not taxed or counted as cash. Joining bonus is taxed in the first year only.",
    "Tax is rounded to the nearest rupee, then 4% cess is added. Surcharge and marginal relief follow the published thresholds. "
    "This is an estimate, not tax advice.",
]
