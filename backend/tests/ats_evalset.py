"""Labelled evaluation set for the ATS keyword extractor + skill matcher.

Each case: a JD, the skills a human reads as required/preferred in it (`expected`, canonical names), the candidate's verified
skills written the way people really write them (`profile`), and the JD skills that candidate truly has (`have`).
`score()` returns precision / recall / F1 for (1) extracting JD keywords and (2) matching them to the verified profile.
"""

from app.jobs.jd_parser import analyze_jd
from app.jobs.matching import _skill_key
from app.services.skills_vocab import implied_umbrellas

CASES = [
    {"title": "SDET", "jd": "Requirements:\n- Strong Selenium WebDriver and Java\n- REST API testing with Rest Assured\n- CI/CD with Jenkins\n"
                            "Nice to have:\n- JMeter\n- Docker",
     "expected": {"Selenium", "Java", "Rest Assured", "Jenkins", "CI/CD", "JMeter", "Docker", "REST", "API Testing"},
     "profile": ["selenium", "Java", "RestAssured", "Jenkins"], "have": {"Selenium", "Java", "Rest Assured", "Jenkins", "CI/CD", "API Testing"}},
    {"title": "Frontend Developer", "jd": "Requirements:\n- 3+ years with ReactJS and TypeScript\n- Modern JS (ES6)\n- Jest unit tests\n"
                                         "- Git and CI / CD pipelines\nNice to have:\n- Node.js\n- GraphQL",
     "expected": {"React", "TypeScript", "JavaScript", "Jest", "Git", "CI/CD", "Node.js", "GraphQL"},
     "profile": ["React.js", "TS", "JS", "Jest", "Git"], "have": {"React", "TypeScript", "JavaScript", "Jest", "Git"}},
    {"title": "Backend Engineer", "jd": "Requirements:\n- Python and FastAPI or Django\n- PostgreSQL / Postgres and Redis\n"
              "- Docker, Kubernetes (K8s)\n"
                                       "- AWS (EC2, S3)\nPreferred:\n- Kafka\n- Terraform",
     "expected": {"Python", "FastAPI", "Django", "PostgreSQL", "Redis", "Docker", "Kubernetes", "AWS", "Kafka", "Terraform"},
     "profile": ["Python", "FastAPI", "Postgres", "Docker", "Amazon Web Services"],
     "have": {"Python", "FastAPI", "PostgreSQL", "Docker", "AWS"}},
    {"title": "QA Automation Engineer", "jd": "Requirements:\n- Playwright or Cypress for end to end tests\n- API automation with Postman\n"
                                            "- BDD with Cucumber\n- Agile / Scrum\n- JIRA\nGood to have:\n- Performance testing with k6",
     "expected": {"Playwright", "Cypress", "API Testing", "Postman", "BDD", "Cucumber", "Agile", "Scrum", "JIRA", "Performance Testing", "k6"},
     "profile": ["Playwright", "Postman", "Cucumber", "Scrum", "Atlassian Jira", "k6"],
     "have": {"Playwright", "Postman", "Cucumber", "Scrum", "JIRA", "k6", "Performance Testing"}},
    {"title": "Data Engineer", "jd": "Requirements:\n- SQL and Python\n- Snowflake or BigQuery\n- Apache Airflow\n- Spark\nPreferred:\n- dbt",
     "expected": {"SQL", "Python", "Snowflake", "BigQuery", "Airflow", "Spark", "dbt"},
     "profile": ["sql", "Python", "Apache Airflow"], "have": {"SQL", "Python", "Airflow"}},
    {"title": "DevOps Engineer", "jd": "Requirements:\n- GitHub Actions or GitLab CI\n- Terraform and Ansible\n- Linux\n- Microsoft Azure\n"
                                      "- Continuous integration and delivery",
     "expected": {"GitHub Actions", "GitLab CI", "Terraform", "Ansible", "Linux", "Azure", "CI/CD"},
     "profile": ["GitHub Actions", "Terraform", "Linux", "Azure"], "have": {"GitHub Actions", "Terraform", "Linux", "Azure", "CI/CD"}},
]


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def score() -> dict:
    tp = fp = fn = mtp = mfp = mfn = 0
    for case in CASES:
        jd = analyze_jd(case["title"], case["jd"])
        got = {_skill_key(s) for s in jd.required_skills + jd.preferred_skills}
        exp = {_skill_key(s) for s in case["expected"]}
        tp, fp, fn = tp + len(got & exp), fp + len(got - exp), fn + len(exp - got)
        have = {_skill_key(s) for s in case["profile"]} | {_skill_key(s) for s in implied_umbrellas(case["profile"])}
        matched = {k for k in got if k in have}
        truth = {_skill_key(s) for s in case["have"]} & got
        mtp, mfp, mfn = mtp + len(matched & truth), mfp + len(matched - truth), mfn + len(truth - matched)
    return {"extraction": _prf(tp, fp, fn), "matching": _prf(mtp, mfp, mfn)}


if __name__ == "__main__":
    print(score())
