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
    "it_services": "IT services & consulting",
    "banking": "Banks & financial services",
    "healthcare": "Healthcare & pharma",
    "industrial": "Industrial, retail & consumer",
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
    host: str = ""  # successfactors / oracle career-site host
    site: str = ""  # oracle: site number
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


def _sr(cid: str, name: str, *tiers: str) -> Company:
    return Company(cid.lower(), name, "smartrecruiters", cid, tiers, careers_url=f"https://jobs.smartrecruiters.com/{cid}")


def _sf(cid: str, host: str, name: str, *tiers: str) -> Company:
    return Company(cid, name, "successfactors", cid, tiers, host=host, careers_url=f"https://{host}/search/")


def _orc(cid: str, host: str, site: str, name: str, *tiers: str) -> Company:
    return Company(cid, name, "oracle", cid, tiers, host=host, site=site,
                   careers_url=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/requisitions")


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
    _sr("Freshworks", "Freshworks", "india", "saas"), _sr("Swiggy", "Swiggy", "india", "consumer"),
    # IT services & consulting
    _sf("hcltech", "careers.hcltech.com", "HCLTech", "it_services", "india"), _sf("wipro", "careers.wipro.com", "Wipro", "it_services", "india"),
    _sf("capgemini", "careers.capgemini.com", "Capgemini", "it_services"), _sf("ey", "careers.ey.com", "EY", "it_services"),
    _wd("pwc", "wd3", "Global_Experienced_Careers", "PwC", "it_services"), _wd("dxctechnology", "wd1", "DXCJobs", "DXC Technology", "it_services"),
    _wd("kyndryl", "wd5", "KyndrylProfessionalCareers", "Kyndryl", "it_services"), _wd("unisys", "wd5", "External", "Unisys", "it_services"),
    _wd("thomsonreuters", "wd5", "External_Career_Site", "Thomson Reuters", "it_services", "saas"),
    _portal("infosys", "Infosys", "https://career.infosys.com/joblist?searchText={q}", "https://career.infosys.com", "it_services", "india"),
    _portal("tcs", "TCS", "https://ibegin.tcs.com/iBegin/jobs/search?keyword={q}", "https://www.tcs.com/careers", "it_services", "india"),
    _portal("cognizant", "Cognizant", "https://careers.cognizant.com/global-en/jobs/?keyword={q}&location={loc}",
            "https://careers.cognizant.com", "it_services"),
    _portal("cgi", "CGI", "https://cgi.njoyn.com/corp/xweb/xweb.asp?page=joblisting&CLID=21001&keywords={q}", "https://www.cgi.com/en/careers",
            "it_services"),
    _portal("techmahindra", "Tech Mahindra", "https://careers.techmahindra.com/", "https://careers.techmahindra.com", "it_services", "india"),
    _portal("ltimindtree", "LTIMindtree", "https://www.ltimindtree.com/careers/", "https://www.ltimindtree.com/careers/", "it_services", "india"),
    _portal("deloitte", "Deloitte", "https://apply.deloitte.com/careers/SearchJobs/{q}", "https://www.deloitte.com/careers", "it_services"),
    _portal("ibm", "IBM", "https://www.ibm.com/careers/search?q={q}", "https://www.ibm.com/careers", "it_services", "big_tech"),
    _portal("tata-elxsi", "Tata Elxsi", "https://www.tataelxsi.com/careers", "https://www.tataelxsi.com/careers", "it_services", "india"),
    # Banks & financial services
    _orc("jpmorgan", "jpmc.fa.oraclecloud.com", "CX_1001", "JPMorgan Chase", "banking", "fintech"),
    _wd("citi", "wd5", "2", "Citi", "banking"), _wd("barclays", "wd3", "External_Career_Site_Barclays", "Barclays", "banking"),
    _wd("db", "wd3", "DBWebsite", "Deutsche Bank", "banking"), _wd("statestreet", "wd1", "Global", "State Street", "banking"),
    _wd("blackrock", "wd1", "BlackRock_Professional", "BlackRock", "banking"), _wd("lseg", "wd3", "Careers", "LSEG", "banking"),
    _wd("fis", "wd5", "SearchJobs", "FIS", "banking", "fintech"), _wd("fiserv", "wd5", "EXT", "Fiserv", "banking", "fintech"),
    _wd("broadridge", "wd5", "Careers", "Broadridge", "banking", "fintech"), _sr("Experian", "Experian", "banking", "fintech"),
    _portal("goldmansachs", "Goldman Sachs", "https://higher.gs.com/results?search={q}&location={loc}", "https://higher.gs.com", "banking"),
    _portal("hdfcbank", "HDFC Bank", "https://www.hdfcbank.com/personal/about-us/careers", "https://www.hdfcbank.com/personal/about-us/careers",
            "banking", "india"),
    # Big tech & enterprise (more)
    _orc("oracle", "eeho.fa.us2.oraclecloud.com", "CX_45001", "Oracle", "big_tech", "saas"),
    _sr("ServiceNow", "ServiceNow", "saas", "big_tech"), _sr("LinkedIn3", "LinkedIn", "big_tech", "consumer"),
    _wd("redhat", "wd5", "jobs", "Red Hat", "saas", "enterprise"), _wd("crowdstrike", "wd5", "crowdstrikecareers", "CrowdStrike", "saas"),
    _wd("micron", "wd1", "External", "Micron", "enterprise"), _wd("marvell", "wd1", "MarvellCareers", "Marvell", "enterprise"),
    _wd("analogdevices", "wd1", "External", "Analog Devices", "enterprise"), _wd("cadence", "wd1", "External_Careers", "Cadence", "enterprise"),
    _wd("motorolasolutions", "wd5", "Careers", "Motorola Solutions", "enterprise"),
    _wd("equinix", "wd1", "External", "Equinix", "enterprise", "saas"),
    _sr("WesternDigital", "Western Digital", "enterprise"), _sr("BoschGroup", "Bosch", "industrial", "enterprise"),
    _sr("Continental", "Continental", "industrial"),
    # Healthcare & pharma
    _wd("pfizer", "wd1", "PfizerCareers", "Pfizer", "healthcare"), _wd("astrazeneca", "wd3", "Careers", "AstraZeneca", "healthcare"),
    _wd("novartis", "wd3", "Novartis_Careers", "Novartis", "healthcare"), _wd("abbott", "wd5", "abbottcareers", "Abbott", "healthcare"),
    _wd("medtronic", "wd1", "MedtronicCareers", "Medtronic", "healthcare"), _wd("philips", "wd3", "jobs-and-careers", "Philips", "healthcare"),
    _wd("elevancehealth", "wd1", "ANT", "Elevance Health", "healthcare"), _sr("AbbVie", "AbbVie", "healthcare"),
    # Industrial, retail & consumer
    _wd("boeing", "wd1", "EXTERNAL_CAREERS", "Boeing", "industrial"), _wd("3m", "wd1", "Search", "3M", "industrial"),
    _wd("pg", "wd5", "1000", "P&G", "industrial"), _wd("nike", "wd1", "nke", "Nike", "industrial", "consumer"),
    _wd("disney", "wd5", "disneycareer", "Disney", "consumer"), _wd("lowes", "wd5", "LWS_External_CS", "Lowe's", "industrial"),
    _wd("homedepot", "wd5", "CareerDepot", "The Home Depot", "industrial"), _wd("chevron", "wd5", "jobs", "Chevron", "industrial"),
    _wd("shell", "wd3", "ShellCareers", "Shell", "industrial"), _sr("Sodexo", "Sodexo", "industrial"),
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
