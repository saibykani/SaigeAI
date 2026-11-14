"""Company type (Service-based / Product-based / Startup / Unknown) from a curated list.

Only companies on the lists below are classified; everything else is "unknown". Nothing is guessed. A user override
(`ctype_user` on the contact, set with PATCH /recruiters/{id}) always wins, and is the only way to mark a startup.
"""

import re

CompanyType = str  # "service" | "product" | "startup" | "unknown"
TYPES = ("service", "product", "startup", "unknown")

SERVICE = [
    "tcs", "tata consultancy services", "infosys", "wipro", "hcl", "hcltech", "hcl technologies", "tech mahindra", "cognizant",
    "accenture", "capgemini", "ltimindtree", "lti", "mindtree", "l&t infotech", "larsen toubro infotech", "mphasis", "hexaware",
    "persistent systems", "coforge", "niit technologies", "birlasoft", "zensar", "ntt data", "ibm", "deloitte", "ey", "ernst young",
    "kpmg", "pwc", "pricewaterhousecoopers", "virtusa", "cyient", "sonata software", "mastek", "happiest minds", "kpit",
    "tata elxsi", "infogain", "genpact", "wns", "firstsource", "ust", "ust global", "dxc", "dxc technology", "atos", "cgi",
    "sopra steria", "thoughtworks", "epam", "globallogic", "tietoevry", "capita", "concentrix", "teleperformance", "hexaware technologies",
    "r systems", "ness digital engineering", "hitachi digital services", "fujitsu", "nagarro", "slk software", "quess", "teamlease",
    "randstad", "adecco", "manpower", "kelly services", "allegis", "experis", "talentpro", "xoriant", "inautix", "igate", "syntel",
]

PRODUCT = [
    "google", "alphabet", "microsoft", "amazon", "aws", "adobe", "salesforce", "atlassian", "flipkart", "swiggy", "zomato", "phonepe",
    "razorpay", "freshworks", "zoho", "paytm", "cred", "meesho", "oracle", "sap", "intuit", "uber", "ola", "ola electric", "apple",
    "meta", "facebook", "netflix", "linkedin", "nvidia", "intel", "amd", "qualcomm", "cisco", "vmware", "servicenow", "workday",
    "paypal", "stripe", "airbnb", "spotify", "twitter", "snap", "dropbox", "slack", "zoom", "okta", "splunk", "databricks",
    "snowflake", "mongodb", "elastic", "red hat", "juniper", "arista", "dell", "dell technologies", "hp", "hewlett packard",
    "samsung", "walmart global tech", "walmart", "myntra", "nykaa", "dream11", "groww", "zerodha", "upstox", "bigbasket",
    "lenskart", "policybazaar", "makemytrip", "ixigo", "cleartrip", "bookmyshow", "byjus", "unacademy", "physicswallah", "zepto",
    "blinkit", "dunzo", "urban company", "cars24", "spinny", "oyo", "browserstack", "postman", "chargebee", "clevertap",
    "moengage", "webengage", "zscaler", "palo alto networks", "fortinet", "crowdstrike", "hashicorp", "gitlab", "github", "jfrog",
    "sprinklr", "druva", "icertis", "hotstar", "jio", "jiosaavn", "sharechat", "dailyhunt", "inmobi", "mobikwik", 
    "bharatpe", "pine labs", "juspay", "ather energy", "tesla", "bosch", "siemens", "honeywell",
    "philips", "ansys", "synopsys", "cadence", "mathworks", "autodesk", "sap labs", "tally", "naukri",
    "info edge", "freshdesk", "darwinbox", "keka", "leadsquared", "gupshup", "yellow ai", "exotel", "kissflow", "whatfix",
]

_NORM = re.compile(r"[^a-z0-9&]+")
_GENERIC_DOMAINS = {"gmail", "googlemail", "yahoo", "outlook", "hotmail", "live", "rediffmail", "icloud", "proton", "protonmail"}


def _norm(text: str) -> str:
    return " " + _NORM.sub(" ", (text or "").lower().replace("&", " & ")).strip() + " "


def _build(entries: list[str]) -> set[str]:
    return {_norm(e).strip() for e in entries}


_SERVICE, _PRODUCT = _build(SERVICE), _build(PRODUCT)


def _hit(norm: str, entries: set[str]) -> bool:
    return any(f" {e} " in norm for e in entries)


def _domain_label(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    parts = email.rsplit("@", 1)[1].lower().split(".")
    if len(parts) < 2:
        return None
    label = parts[-3] if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "ac") else parts[-2]
    return None if label in _GENERIC_DOMAINS else label


def auto_company_type(company: str | None, email: str | None = None) -> CompanyType:
    """service / product when the company (or its email domain) is on the curated lists, else unknown."""
    norm = _norm(company or "")
    s, p = _hit(norm, _SERVICE), _hit(norm, _PRODUCT)
    if s != p:
        return "service" if s else "product"
    if not (s or p):
        label = _domain_label(email)
        if label in _SERVICE:
            return "service"
        if label in _PRODUCT:
            return "product"
    return "unknown"


def effective_type(doc: dict) -> CompanyType:
    return doc.get("ctype_user") or doc.get("ctype") or auto_company_type(doc.get("company"), doc.get("email"))
