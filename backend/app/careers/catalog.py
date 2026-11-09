"""Company career-portal catalogue.

Two kinds of entries:

- **api** companies publish their openings through a public, unauthenticated careers API: Greenhouse, Lever and
  Ashby job boards, Workday career sites (the `wday/cxs` JSON the public site itself calls) and Amazon Jobs
  (`search.json`). Saige reads those on a schedule. Each one was checked to respond when it was added; a
  company that moves ATS shows up as "unavailable" in the scan report, not as an error.
- **portal** companies (Google, Meta, Apple, Microsoft, Netflix, ...) offer no public jobs API. Saige never scrapes
  them; it builds a deep link into their own careers search, filtered by the user's role and location, so it
  takes one click to look.

Request URLs are always built from these fixed hosts plus validated ids (no user-supplied hosts, so no SSRF).
"""

from dataclasses import dataclass, field
from urllib.parse import quote_plus

TIERS: dict[str, str] = {
    "faang": "FAANG / MAANG",
    "big_tech": "Big tech",
    "ai": "AI labs",
    "fintech": "Fintech",
    "saas": "SaaS & cloud",
    "consumer": "Consumer internet",
    "enterprise": "Enterprise & semiconductors",
    "india": "India product companies",
}


@dataclass(frozen=True)
class Company:
    id: str
    name: str
    provider: str  # greenhouse | lever | ashby | workday | amazon | portal
    board: str = ""  # board token / tenant
    tiers: tuple[str, ...] = ()
    wd_host: str = ""  # workday: "wd5"
    wd_site: str = ""  # workday: career site id
    portal: str = ""  # portal: search URL template with {q} and {loc}
    careers_url: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def is_api(self) -> bool:
        return self.provider != "portal"


def _gh(board: str, name: str, *tiers: str) -> Company:
    return Company(board, name, "greenhouse", board, tiers, careers_url=f"https://boards.greenhouse.io/{board}")


def _lv(board: str, name: str, *tiers: str) -> Company:
    return Company(board, name, "lever", board, tiers, careers_url=f"https://jobs.lever.co/{board}")


def _ab(board: str, name: str, *tiers: str) -> Company:
    return Company(board, name, "ashby", board, tiers, careers_url=f"https://jobs.ashbyhq.com/{board}")


def _wd(tenant: str, host: str, site: str, name: str, *tiers: str) -> Company:
    return Company(tenant, name, "workday", tenant, tiers, wd_host=host, wd_site=site,
                   careers_url=f"https://{tenant}.{host}.myworkdayjobs.com/en-US/{site}")


def _portal(cid: str, name: str, template: str, careers: str, *tiers: str) -> Company:
    return Company(cid, name, "portal", "", tiers, portal=template, careers_url=careers)


COMPANIES: list[Company] = [
    # FAANG / MAANG
    Company("amazon", "Amazon", "amazon", "amazon", ("faang", "big_tech"), careers_url="https://www.amazon.jobs"),
    _portal("meta", "Meta", "https://www.metacareers.com/jobs?q={q}&offices[0]={loc}", "https://www.metacareers.com/jobs", "faang", "big_tech"),
    _portal("google", "Google", "https://www.google.com/about/careers/applications/jobs/results/?q={q}&location={loc}",
            "https://www.google.com/about/careers/applications/jobs/results/", "faang", "big_tech"),
    _portal("apple", "Apple", "https://jobs.apple.com/en-us/search?search={q}%20{loc}", "https://jobs.apple.com", "faang", "big_tech"),
    _portal("netflix", "Netflix", "https://explore.jobs.netflix.net/careers?query={q}&location={loc}",
            "https://explore.jobs.netflix.net/careers", "faang", "big_tech", "consumer"),
    _portal("microsoft", "Microsoft", "https://jobs.careers.microsoft.com/global/en/search?q={q}&lc={loc}",
            "https://jobs.careers.microsoft.com/global/en/search", "faang", "big_tech"),
    # Big tech, enterprise & semiconductors (Workday)
    _wd("nvidia", "wd5", "NVIDIAExternalCareerSite", "NVIDIA", "big_tech", "enterprise", "ai"),
    _wd("salesforce", "wd12", "External_Career_Site", "Salesforce", "big_tech", "saas"),
    _wd("adobe", "wd5", "external_experienced", "Adobe", "big_tech", "saas"),
    _wd("intel", "wd1", "External", "Intel", "enterprise"),
    _wd("cisco", "wd5", "Cisco_Careers", "Cisco", "big_tech", "enterprise"),
    _wd("paypal", "wd1", "jobs", "PayPal", "fintech", "big_tech"),
    _wd("mastercard", "wd1", "CorporateCareers", "Mastercard", "fintech", "enterprise"),
    _wd("broadcom", "wd1", "External_Career", "Broadcom", "enterprise"),
    _wd("hp", "wd5", "ExternalCareerSite", "HP", "enterprise"),
    _wd("target", "wd5", "targetcareers", "Target", "enterprise", "consumer"),
    _wd("accenture", "wd103", "AccentureCareers", "Accenture", "enterprise"),
    _wd("workday", "wd5", "Workday", "Workday", "saas"),
    _wd("autodesk", "wd1", "Ext", "Autodesk", "saas"),
    # AI labs
    _gh("anthropic", "Anthropic", "ai"), _ab("openai", "OpenAI", "ai"), _gh("scaleai", "Scale AI", "ai"),
    _ab("perplexity", "Perplexity", "ai"), _ab("cursor", "Cursor", "ai"), _gh("databricks", "Databricks", "ai", "saas"),
    # Consumer internet
    _gh("airbnb", "Airbnb", "consumer", "big_tech"), _gh("pinterest", "Pinterest", "consumer"), _gh("reddit", "Reddit", "consumer"),
    _gh("lyft", "Lyft", "consumer"), _gh("discord", "Discord", "consumer"), _gh("instacart", "Instacart", "consumer"),
    _gh("duolingo", "Duolingo", "consumer"), _lv("spotify", "Spotify", "consumer", "big_tech"), _gh("dropbox", "Dropbox", "consumer", "saas"),
    # Fintech
    _gh("stripe", "Stripe", "fintech"), _gh("coinbase", "Coinbase", "fintech"), _gh("robinhood", "Robinhood", "fintech"),
    _gh("brex", "Brex", "fintech"), _gh("affirm", "Affirm", "fintech"), _gh("chime", "Chime", "fintech"),
    _gh("toast", "Toast", "fintech"), _ab("ramp", "Ramp", "fintech"), _lv("zeta", "Zeta", "fintech", "india"),
    # SaaS & cloud
    _gh("mongodb", "MongoDB", "saas"), _gh("cloudflare", "Cloudflare", "saas"), _gh("datadog", "Datadog", "saas"),
    _gh("elastic", "Elastic", "saas"), _gh("twilio", "Twilio", "saas"), _gh("gitlab", "GitLab", "saas"),
    _gh("zscaler", "Zscaler", "saas"), _gh("okta", "Okta", "saas"), _gh("figma", "Figma", "saas"), _gh("asana", "Asana", "saas"),
    _gh("samsara", "Samsara", "saas"), _gh("rubrik", "Rubrik", "saas"), _gh("newrelic", "New Relic", "saas"),
    _gh("gusto", "Gusto", "saas"), _gh("flexport", "Flexport", "saas"), _lv("palantir", "Palantir", "saas", "enterprise"),
    _ab("notion", "Notion", "saas"), _ab("linear", "Linear", "saas"), _ab("supabase", "Supabase", "saas"),
    _lv("jumpcloud", "JumpCloud", "saas"),
    # India product companies
    _gh("groww", "Groww", "india", "fintech"), _gh("hackerrank", "HackerRank", "india"), _gh("druva", "Druva", "india", "saas"),
    _lv("meesho", "Meesho", "india", "consumer"), _lv("cred", "CRED", "india", "fintech"),
    _lv("mindtickle", "Mindtickle", "india", "saas"), _ab("atlan", "Atlan", "india", "saas"),
]

BY_ID: dict[str, Company] = {co.id: co for co in COMPANIES}
assert len(BY_ID) == len(COMPANIES), "duplicate company id in catalogue"


def select(tiers: list[str] | None = None, ids: list[str] | None = None, api_only: bool = False) -> list[Company]:
    """Companies in any of `tiers` and/or listed in `ids`; everything when both are empty."""
    tiers, ids = [t for t in tiers or [] if t], [i for i in ids or [] if i]
    out = [co for co in COMPANIES if (not tiers and not ids) or co.id in ids or set(co.tiers) & set(tiers)]
    return [co for co in out if co.is_api] if api_only else out


def portal_link(co: Company, role: str, location: str | None) -> str:
    if not co.portal:
        return co.careers_url
    return co.portal.format(q=quote_plus(role or ""), loc=quote_plus(location or ""))


def public(co: Company, role: str = "", location: str | None = None) -> dict:
    return {"id": co.id, "name": co.name, "provider": co.provider, "tiers": list(co.tiers), "api": co.is_api,
            "careers_url": co.careers_url, "search_url": portal_link(co, role, location) if role else co.careers_url}
