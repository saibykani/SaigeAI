"""Curated skill vocabulary used for resume parsing, categorisation and truth validation.

The vocabulary only *recognises* skill names in text; it never grants a skill to a candidate.
"""

import re

# canonical name -> profile skills category
SKILL_CATEGORIES: dict[str, str] = {
    # languages
    "Java": "programming_languages", "Python": "programming_languages",
    "JavaScript": "programming_languages", "TypeScript": "programming_languages",
    "C#": "programming_languages", "C++": "programming_languages", "Go": "programming_languages",
    "Kotlin": "programming_languages", "Ruby": "programming_languages",
    "SQL": "programming_languages", "Groovy": "programming_languages",
    "Scala": "programming_languages",
    # automation / testing frameworks
    "Selenium": "automation", "Playwright": "automation", "Cypress": "automation",
    "Appium": "automation", "WebdriverIO": "automation", "Puppeteer": "automation",
    "TestNG": "frameworks", "JUnit": "frameworks", "Cucumber": "frameworks",
    "PyTest": "frameworks", "Mocha": "frameworks", "Jest": "frameworks", "BDD": "frameworks",
    "Spring Boot": "frameworks", "React": "frameworks", "Node.js": "frameworks",
    "Robot Framework": "frameworks", "Serenity": "frameworks", "Karate": "api_testing",
    # API testing
    "Rest Assured": "api_testing", "Postman": "api_testing", "SoapUI": "api_testing",
    "API Testing": "api_testing", "REST": "api_testing", "GraphQL": "api_testing",
    "Swagger": "api_testing", "Newman": "api_testing",
    # performance
    "JMeter": "performance_testing", "Gatling": "performance_testing",
    "LoadRunner": "performance_testing", "k6": "performance_testing",
    "Locust": "performance_testing", "Performance Testing": "performance_testing",
    "Load Testing": "performance_testing", "BlazeMeter": "performance_testing",
    # manual / process
    "Manual Testing": "manual_testing", "Regression Testing": "manual_testing",
    "Functional Testing": "manual_testing", "UAT": "manual_testing",
    "Test Case Design": "manual_testing", "Exploratory Testing": "manual_testing",
    "Smoke Testing": "manual_testing", "Agile": "secondary", "Scrum": "secondary",
    # tools
    "JIRA": "testing_tools", "TestRail": "testing_tools", "Zephyr": "testing_tools",
    "qTest": "testing_tools", "ALM": "testing_tools", "Allure": "testing_tools",
    "Extent Reports": "testing_tools", "Git": "tools", "GitHub": "tools", "Maven": "tools",
    "Gradle": "tools", "Docker": "tools", "Kubernetes": "tools", "Confluence": "tools",
    "Charles Proxy": "tools", "Fiddler": "tools", "BrowserStack": "tools",
    "Sauce Labs": "tools", "Linux": "tools",
    # CI/CD
    "Jenkins": "ci_cd", "GitHub Actions": "ci_cd", "GitLab CI": "ci_cd",
    "Azure DevOps": "ci_cd", "CircleCI": "ci_cd", "Bamboo": "ci_cd", "CI/CD": "ci_cd",
    # cloud
    "AWS": "cloud", "Azure": "cloud", "GCP": "cloud",
    # databases
    "MySQL": "databases", "PostgreSQL": "databases", "MongoDB": "databases",
    "Oracle": "databases", "SQL Server": "databases", "Redis": "databases",
}

ALIASES: dict[str, str] = {
    "js": "JavaScript", "ts": "TypeScript", "golang": "Go", "c sharp": "C#",
    "restassured": "Rest Assured", "rest-assured": "Rest Assured", "rest api": "REST",
    "restful": "REST", "api automation": "API Testing", "selenium webdriver": "Selenium",
    "webdriver": "Selenium", "apache jmeter": "JMeter", "junit5": "JUnit", "junit 5": "JUnit",
    "nodejs": "Node.js","postgres": "PostgreSQL", "mssql": "SQL Server",
    "amazon web services": "AWS", "google cloud": "GCP", "microsoft azure": "Azure",
    "github actions": "GitHub Actions", "gitlab": "GitLab CI", "k8s": "Kubernetes",
    "ci cd": "CI/CD", "cicd": "CI/CD", "atlassian jira": "JIRA", "jira": "JIRA",
    "load runner": "LoadRunner", "pytest": "PyTest", "testng": "TestNG", "soap ui": "SoapUI",
}

_CANON_BY_KEY = {k.lower(): k for k in SKILL_CATEGORIES}


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().strip(".,;:()[]"))


def canonical(value: str) -> str:
    """Return the canonical skill name if recognised, else the cleaned original."""
    key = normalize_key(value)
    if key in ALIASES:
        return ALIASES[key]
    return _CANON_BY_KEY.get(key, value.strip())


# Umbrella skills implied by having a concrete tool in that category (Rest Assured -> API Testing).
UMBRELLA_SKILLS = {"api_testing": "API Testing", "ci_cd": "CI/CD",
                   "performance_testing": "Performance Testing", "manual_testing": "Manual Testing"}


def implied_umbrellas(skills: list[str], categories_with_values: list[str] = ()) -> set[str]:
    """Umbrella skills a candidate truthfully has because they list a concrete tool in that area."""
    implied = {UMBRELLA_SKILLS[cat] for s in skills if (cat := category_of(s)) in UMBRELLA_SKILLS}
    implied |= {UMBRELLA_SKILLS[c] for c in categories_with_values if c in UMBRELLA_SKILLS}
    return implied


def category_of(skill: str) -> str:
    return SKILL_CATEGORIES.get(canonical(skill), "secondary")


def _pattern(term: str) -> re.Pattern[str]:
    # Word-ish boundaries that tolerate symbols like C#, C++, Node.js, CI/CD
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9+#])", re.IGNORECASE)


# Short/ambiguous terms that are only matched case-sensitively to avoid false positives.
_CASE_SENSITIVE = {"REST", "ALM", "UAT", "SQL", "BDD", "AWS", "GCP", "Git", "React", "Oracle"}
# Terms that are ordinary English words; recognised only via unambiguous aliases (e.g. golang).
_NOT_SCANNED = {"Go"}
_PATTERNS: list[tuple[str, re.Pattern[str]]] = []
for _term in list(SKILL_CATEGORIES) + list(ALIASES):
    if _term in _NOT_SCANNED:
        continue
    _canon = canonical(_term)
    if _term in _CASE_SENSITIVE:
        _PATTERNS.append((_canon, re.compile(r"(?<![A-Za-z0-9])" + re.escape(_term)
                                             + r"(?![A-Za-z0-9+#])")))
    else:
        _PATTERNS.append((_canon, _pattern(_term)))


def find_skills(text: str) -> list[str]:
    """Recognised vocabulary skills mentioned anywhere in `text` (canonical, de-duplicated)."""
    found: dict[str, None] = {}
    for canon, pat in _PATTERNS:
        if pat.search(text):
            found[canon] = None
    return list(found)
