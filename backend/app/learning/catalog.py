"""Static catalogue of FREE learning resources (no scraping). Unknown skills fall back to search links."""

from urllib.parse import quote_plus


def _r(title: str, url: str, provider: str, kind: str, hours: int) -> dict:
    return {"title": title, "url": url, "provider": provider, "kind": kind, "hours": hours}


FCC = "https://www.freecodecamp.org/learn"
CATALOG: dict[str, dict] = {
    "python": {"hours": 30, "resources": [
        _r("The Python Tutorial", "https://docs.python.org/3/tutorial/", "Python.org", "docs", 10),
        _r("Scientific Computing with Python", f"{FCC}/scientific-computing-with-python/", "freeCodeCamp", "course", 20)]},
    "javascript": {"hours": 30, "resources": [
        _r("JavaScript Guide", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide", "MDN", "docs", 12),
        _r("JavaScript Algorithms and Data Structures", f"{FCC}/javascript-algorithms-and-data-structures-v8/", "freeCodeCamp", "course", 20)]},
    "typescript": {"hours": 12, "resources": [
        _r("The TypeScript Handbook", "https://www.typescriptlang.org/docs/handbook/intro.html", "TypeScript", "docs", 8),
        _r("TypeScript course", "https://www.youtube.com/watch?v=30LWjhZzg50", "freeCodeCamp (YouTube)", "video", 5)]},
    "react": {"hours": 20, "resources": [
        _r("Learn React", "https://react.dev/learn", "react.dev", "docs", 10),
        _r("Front End Development Libraries", f"{FCC}/front-end-development-libraries/", "freeCodeCamp", "course", 12)]},
    "next.js": {"hours": 12, "resources": [_r("Learn Next.js", "https://nextjs.org/learn", "Vercel", "course", 10)]},
    "node.js": {"hours": 15, "resources": [
        _r("Learn Node.js", "https://nodejs.org/en/learn", "Node.js", "docs", 8),
        _r("Back End Development and APIs", f"{FCC}/back-end-development-and-apis/", "freeCodeCamp", "course", 12)]},
    "java": {"hours": 30, "resources": [
        _r("Dev.java Learn", "https://dev.java/learn/", "Oracle", "docs", 15),
        _r("Java Programming MOOC", "https://java-programming.mooc.fi/", "University of Helsinki", "course", 25)]},
    "sql": {"hours": 15, "resources": [
        _r("Relational Database", f"{FCC}/relational-database/", "freeCodeCamp", "course", 12),
        _r("SQLBolt interactive lessons", "https://sqlbolt.com/", "SQLBolt", "practice", 4)]},
    "aws": {"hours": 25, "resources": [
        _r("AWS Skill Builder (free digital courses)", "https://skillbuilder.aws/", "AWS", "course", 15),
        _r("AWS Cloud Practitioner course", "https://www.youtube.com/watch?v=NhDYbskXRgc", "freeCodeCamp (YouTube)", "video", 14)]},
    "azure": {"hours": 20, "resources": [
        _r("Azure Fundamentals (AZ-900) path", "https://learn.microsoft.com/en-us/training/paths/microsoft-azure-fundamentals-describe-cloud-concepts/",
           "Microsoft Learn", "course", 10)]},
    "gcp": {"hours": 20, "resources": [
        _r("Google Cloud Skills Boost (free labs)", "https://www.cloudskillsboost.google/", "Google Cloud", "course", 15)]},
    "docker": {"hours": 10, "resources": [
        _r("Docker Get Started", "https://docs.docker.com/get-started/", "Docker", "docs", 5),
        _r("Docker course", "https://www.youtube.com/watch?v=fqMOX6JJhGo", "freeCodeCamp (YouTube)", "video", 2)]},
    "kubernetes": {"hours": 20, "resources": [
        _r("Kubernetes Basics", "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "Kubernetes", "docs", 6),
        _r("Introduction to Kubernetes (audit)", "https://www.edx.org/learn/kubernetes/the-linux-foundation-introduction-to-kubernetes",
           "Linux Foundation (edX)", "course", 14)]},
    "git": {"hours": 6, "resources": [_r("Pro Git book", "https://git-scm.com/book/en/v2", "git-scm", "docs", 6)]},
    "linux": {"hours": 15, "resources": [
        _r("Introduction to Linux (audit)", "https://www.edx.org/learn/linux/the-linux-foundation-introduction-to-linux",
           "Linux Foundation (edX)", "course", 15)]},
    "selenium": {"hours": 12, "resources": [_r("Selenium documentation", "https://www.selenium.dev/documentation/", "Selenium", "docs", 8)]},
    "playwright": {"hours": 10, "resources": [_r("Playwright docs: Getting started", "https://playwright.dev/docs/intro", "Playwright", "docs", 8)]},
    "cypress": {"hours": 8, "resources": [_r("Cypress docs", "https://docs.cypress.io/app/get-started/why-cypress", "Cypress", "docs", 8)]},
    "api testing": {"hours": 8, "resources": [_r("Postman Academy", "https://academy.postman.com/", "Postman", "course", 8)]},
    "postman": {"hours": 6, "resources": [_r("Postman Academy", "https://academy.postman.com/", "Postman", "course", 6)]},
    "machine learning": {"hours": 40, "resources": [
        _r("Machine Learning Crash Course", "https://developers.google.com/machine-learning/crash-course", "Google", "course", 15),
        _r("Machine Learning Specialization (audit)", "https://www.coursera.org/specializations/machine-learning-introduction",
           "Coursera (audit)", "course", 30)]},
    "pandas": {"hours": 8, "resources": [
        _r("pandas Getting started", "https://pandas.pydata.org/docs/getting_started/index.html", "pandas", "docs", 8)]},
    "power bi": {"hours": 15, "resources": [
        _r("Power BI learning paths", "https://learn.microsoft.com/en-us/training/powerplatform/power-bi", "Microsoft Learn", "course", 15)]},
    "excel": {"hours": 10, "resources": [
        _r("Excel video training", "https://support.microsoft.com/en-us/office/excel-video-training-9bc05390-e94c-46af-a5b3-d7c22f6990bb",
           "Microsoft", "video", 6)]},
    "tableau": {"hours": 12, "resources": [_r("Tableau free training videos", "https://www.tableau.com/learn/training", "Tableau", "video", 10)]},
    "google analytics": {"hours": 8, "resources": [
        _r("Google Analytics certification", "https://skillshop.withgoogle.com/", "Google Skillshop", "course", 8)]},
    "google ads": {"hours": 8, "resources": [_r("Google Ads certifications", "https://skillshop.withgoogle.com/", "Google Skillshop", "course", 8)]},
    "seo": {"hours": 8, "resources": [
        _r("SEO Starter Guide", "https://developers.google.com/search/docs/fundamentals/seo-starter-guide", "Google Search Central", "docs", 4)]},
    "ci/cd": {"hours": 8, "resources": [_r("GitHub Actions docs", "https://docs.github.com/en/actions", "GitHub", "docs", 6)]},
    "jenkins": {"hours": 8, "resources": [_r("Jenkins tutorials", "https://www.jenkins.io/doc/tutorials/", "Jenkins", "docs", 6)]},
    "terraform": {"hours": 10, "resources": [
        _r("Terraform tutorials", "https://developer.hashicorp.com/terraform/tutorials", "HashiCorp", "docs", 10)]},
    "mongodb": {"hours": 10, "resources": [_r("MongoDB University (free)", "https://learn.mongodb.com/", "MongoDB", "course", 10)]},
    "fastapi": {"hours": 8, "resources": [_r("FastAPI tutorial", "https://fastapi.tiangolo.com/tutorial/", "FastAPI", "docs", 8)]},
    "django": {"hours": 12, "resources": [_r("Django tutorial", "https://docs.djangoproject.com/en/stable/intro/tutorial01/", "Django", "docs", 8)]},
    "spring boot": {"hours": 15, "resources": [_r("Spring guides", "https://spring.io/guides", "Spring", "docs", 12)]},
    "c#": {"hours": 25, "resources": [_r("Learn C#", "https://learn.microsoft.com/en-us/dotnet/csharp/", "Microsoft Learn", "docs", 20)]},
    "go": {"hours": 15, "resources": [_r("A Tour of Go", "https://go.dev/tour/", "go.dev", "practice", 8)]},
    "rest api": {"hours": 6, "resources": [_r("APIs and microservices", f"{FCC}/back-end-development-and-apis/", "freeCodeCamp", "course", 6)]},
    "graphql": {"hours": 6, "resources": [_r("Learn GraphQL", "https://graphql.org/learn/", "GraphQL", "docs", 5)]},
    "html": {"hours": 8, "resources": [_r("Responsive Web Design", f"{FCC}/2022/responsive-web-design/", "freeCodeCamp", "course", 15)]},
    "css": {"hours": 10, "resources": [_r("Learn CSS", "https://web.dev/learn/css", "web.dev (Google)", "course", 10)]},
    "agile": {"hours": 4, "resources": [_r("Scrum Guide", "https://scrumguides.org/scrum-guide.html", "Scrum.org", "docs", 2)]},
    "jira": {"hours": 4, "resources": [_r("Atlassian University (free)", "https://university.atlassian.com/", "Atlassian", "course", 4)]},
    "figma": {"hours": 8, "resources": [_r("Figma Learn", "https://help.figma.com/hc/en-us/categories/360002051613", "Figma", "docs", 6)]},
    "data structures": {"hours": 30, "resources": [
        _r("Data Structures (audit)", "https://www.coursera.org/learn/data-structures", "Coursera (audit)", "course", 25)]},
    "generative ai": {"hours": 10, "resources": [
        _r("Introduction to Generative AI", "https://www.cloudskillsboost.google/course_templates/536", "Google Cloud", "course", 2),
        _r("Generative AI for Beginners", "https://microsoft.github.io/generative-ai-for-beginners/", "Microsoft", "course", 10)]},
}
ALIASES = {"js": "javascript", "ts": "typescript", "reactjs": "react", "react.js": "react", "node": "node.js", "nodejs": "node.js",
           "nextjs": "next.js", "amazon web services": "aws", "google cloud": "gcp", "k8s": "kubernetes", "ml": "machine learning",
           "golang": "go", "rest": "rest api", "rest apis": "rest api", "restful api": "rest api", "github actions": "ci/cd",
           "html5": "html", "css3": "css", "scrum": "agile", "genai": "generative ai", "llm": "generative ai", "dsa": "data structures",
           "postgresql": "sql", "mysql": "sql", "dotnet": "c#", ".net": "c#"}

# Skills commonly expected for a target role (used to widen the gap list when few jobs are saved).
ROLE_SKILLS: dict[str, list[str]] = {
    "sdet": ["selenium", "playwright", "api testing", "ci/cd", "java", "python"],
    "qa": ["selenium", "api testing", "postman", "sql", "jira", "agile"],
    "test": ["selenium", "api testing", "ci/cd"],
    "frontend": ["javascript", "typescript", "react", "next.js", "css"],
    "front end": ["javascript", "typescript", "react", "css"],
    "backend": ["python", "node.js", "sql", "docker", "rest api"],
    "full stack": ["javascript", "react", "node.js", "sql", "docker"],
    "devops": ["docker", "kubernetes", "terraform", "ci/cd", "aws", "linux"],
    "cloud": ["aws", "azure", "terraform", "kubernetes"],
    "data analyst": ["sql", "excel", "power bi", "tableau", "python"],
    "data scientist": ["python", "pandas", "machine learning", "sql"],
    "data engineer": ["python", "sql", "aws", "docker"],
    "machine learning": ["python", "machine learning", "pandas", "generative ai"],
    "marketing": ["google analytics", "google ads", "seo"],
    "designer": ["figma"],
    "java": ["java", "spring boot", "sql"],
    "python": ["python", "fastapi", "django", "sql"],
}


def key_of(skill: str) -> str:
    k = skill.strip().lower()
    return ALIASES.get(k, k)


def resources_for(skill: str) -> tuple[list[dict], int]:
    """(resources with stable ids, estimated hours)."""
    entry = CATALOG.get(key_of(skill))
    if entry:
        res, hours = entry["resources"], entry["hours"]
    else:
        q = quote_plus(skill)
        res = [_r(f"{skill} on freeCodeCamp", f"https://www.freecodecamp.org/news/search/?query={q}", "freeCodeCamp", "search", 4),
               _r(f"{skill} on Microsoft Learn", f"https://learn.microsoft.com/en-us/search/?terms={q}", "Microsoft Learn", "search", 4),
               _r(f"{skill} courses (audit for free)", f"https://www.coursera.org/search?query={q}", "Coursera (audit)", "search", 6),
               _r(f"{skill} tutorials on YouTube", f"https://www.youtube.com/results?search_query={q}+tutorial", "YouTube", "search", 3)]
        hours = 10
    return [{**r, "id": f"r{i}"} for i, r in enumerate(res)], hours
