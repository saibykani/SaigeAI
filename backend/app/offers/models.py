from typing import Literal

from pydantic import BaseModel, Field

Money = Field(default=0.0, ge=0, le=10**10)


class OfferInput(BaseModel):
    """One offer or current salary. Every amount is per year in rupees."""

    name: str = Field(default="Offer", max_length=80)
    company: str = Field(default="", max_length=120)
    basic: float = Money
    hra: float = Money
    special: float = Money
    lta: float = Money
    other_allowances: float = Money
    employer_pf: float | None = Field(default=None, ge=0, le=10**10)  # None = same as employee PF
    gratuity: float = Money
    insurance: float = Money
    employer_nps: float = Money
    variable: float = Money
    variable_payout_pct: float = Field(default=100.0, ge=0, le=300)
    joining_bonus: float = Money
    esop_annual: float = Money
    city: Literal["metro", "non_metro"] = "metro"
    rent_paid: float = Money
    pf_mode: Literal["12pct", "capped"] = "12pct"
    sec80c: float = Money  # ELSS, LIC, tuition... (employee PF is added automatically)
    sec80d: float = Money
    employee_nps: float = Money  # 80CCD(1B)
    home_loan_interest: float = Money
    lta_claimed: float = Money
    state: str = "KA"
    pt_annual: float | None = Field(default=None, ge=0, le=100_000)


class CompareRequest(BaseModel):
    offers: list[OfferInput] = Field(min_length=1, max_length=3)
    current: OfferInput | None = None
    notice_days: int = Field(default=0, ge=0, le=365)
    buyout_basis: Literal["basic", "gross"] = "basic"


class SplitRequest(BaseModel):
    ctc: float = Field(gt=0, le=10**10)
    variable_pct: float = Field(default=0.0, ge=0, le=60)  # % of CTC that is variable
    basic_pct: float = Field(default=40.0, ge=10, le=70)
    hra_pct_of_basic: float = Field(default=50.0, ge=0, le=60)
    insurance: float = Field(default=0.0, ge=0, le=10**7)
    pf_mode: Literal["12pct", "capped"] = "12pct"


class ParseRequest(BaseModel):
    text: str = Field(max_length=6000)


class OfferMeta(BaseModel):
    """Decision details around a saved offer. Everything is user-entered; blanks stay unknown and are never guessed."""

    location: str = Field(default="", max_length=120)
    commute_minutes: int = Field(default=0, ge=0, le=300)  # one way
    wfh_days: int = Field(default=0, ge=0, le=5)  # work-from-home days per week
    notice_days: int = Field(default=0, ge=0, le=365)
    buyout_amount: float = Field(default=0.0, ge=0, le=10**8)
    benefits: list[str] = Field(default_factory=list, max_length=20)
    health_cover: float = Field(default=0.0, ge=0, le=10**8)
    learning_budget: float = Field(default=0.0, ge=0, le=10**7)  # per year
    growth_notes: str = Field(default="", max_length=1500)
    esop_grant_value: float = Field(default=0.0, ge=0, le=10**10)  # total grant at the value YOU believe in
    esop_vesting_years: int = Field(default=4, ge=1, le=8)
    esop_cliff_months: int = Field(default=12, ge=0, le=48)
    growth_rating: int | None = Field(default=None, ge=0, le=10)
    learning_rating: int | None = Field(default=None, ge=0, le=10)
    user_rating: int | None = Field(default=None, ge=0, le=10)  # your gut feeling
    application_id: str | None = Field(default=None, max_length=64)


class SavedOffer(BaseModel):
    input: OfferInput
    meta: OfferMeta = Field(default_factory=OfferMeta)
