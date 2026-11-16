"""Offline fixtures for the resume / email quality harness: one verified profile and five realistic job posts."""

PROFILE = {
    "personal": {"name": "Asha Rao", "email": "asha@example.com", "phone": "+91 90000 00000", "current_designation": "Senior QA Engineer",
                 "current_company": "Finserve", "total_experience_years": 4.5, "notice_period_days": 30, "current_ctc": 12,
                 "expected_ctc": 18, "ctc_currency": "INR", "current_location": "Hyderabad",
                 "linkedin_url": "https://www.linkedin.com/in/asharao"},
    "skills": {"programming_languages": ["Java", "SQL", "Python"], "automation": ["Selenium", "TestNG"],
               "api_testing": ["API Testing", "RestAssured", "Postman"], "ci_cd": ["Jenkins", "Git"],
               "performance_testing": ["JMeter", "Performance Testing", "Load Testing"], "databases": ["MySQL"],
               "tools": ["Jira", "Grafana"]},
    "preferences": {"target_roles": ["Performance Test Engineer", "SDET"]},
    "knowledge": {
        "professional_summary": "QA engineer focused on performance and automation.",
        "domains": ["Fintech", "Banking"],
        "experience": [
            {"company": "Finserve", "title": "Senior QA Engineer", "start_date": "Jan 2023", "is_current": True,
             "responsibilities": ["Worked on load testing of payment APIs using JMeter and Grafana dashboards",
                                  "Responsible for creating Selenium and TestNG regression suites in Java",
                                  "Involved in Jenkins pipeline setup for nightly test runs",
                                  "Attended daily stand-ups"],
             "achievements": ["Reduced API response time by 35% after bottleneck analysis with JMeter",
                              "Automated 120 regression cases, cutting release testing from 3 days to 1 day"],
             "technologies": ["JMeter", "Selenium", "Java", "Jenkins"]},
            {"company": "Brightsoft", "title": "QA Engineer", "start_date": "Jun 2021", "end_date": "Dec 2022",
             "responsibilities": ["Helped to write test cases for banking web applications",
                                  "Handled API testing with Postman and RestAssured"],
             "achievements": [], "technologies": ["Postman", "MySQL"]},
        ],
        "projects": [
            {"name": "Payments Dashboard", "highlights": ["Built Grafana dashboards"], "technologies": ["Grafana", "MySQL"]},
            {"name": "Load Test Suite", "highlights": ["Created JMeter scripts for 500 concurrent users"], "technologies": ["JMeter", "Jenkins"]},
        ],
        "education": [{"degree": "B.Tech", "institution": "JNTU", "field": "Computer Science"}],
    },
}

JDS = {
    "perf": {"title": "#We're Hiring Performance Test Engineer | Hyderabad", "role": "Performance Test Engineer", "company": "Acme Pay",
             "text": "#We're Hiring Performance Test Engineer | Hyderabad\n\nAbout us\nAcme Pay builds fintech payment products.\n\n"
                     "Responsibilities\n- Design and run load testing and performance testing with JMeter\n- Monitor results in Grafana\n"
                     "- Integrate tests into Jenkins pipelines\n\nRequirements\n- 3-5 years of experience in performance testing\n"
                     "- Strong JMeter and Java skills\n- REST API testing with Postman\n- Kubernetes and Gatling experience\n\n"
                     "Nice to have\n- Selenium\n\nSend your CV to hr@acmepay.com. Contact: Priya Sharma"},
    "sdet": {"title": "SDET", "role": "SDET", "company": "Globex",
             "text": "Responsibilities\n- Build Selenium and RestAssured automation frameworks in Java\n- Run suites in Jenkins\n\n"
                     "Requirements\n- 3+ years of test automation\n- Java, Selenium, API testing\n- Cypress is a plus\n"},
    "data": {"title": "Data Analyst", "role": "Data Analyst", "company": "Initech",
             "text": "Requirements\n- 2+ years as a Data Analyst\n- SQL and Python\n- Tableau or Power BI dashboards\n- Excel\n"},
    "java": {"title": "Java Developer", "role": "Java Developer", "company": "Hooli",
             "text": "Responsibilities\n- Develop services in Java with Spring Boot and MySQL\n- Use Git and Jenkins\n\n"
                     "Requirements\n- 3+ years of Java development\n- SQL, REST APIs, Docker\n"},
    "hashtag": {"title": "#hiring SDET - Automation", "role": "SDET", "company": "Umbrella",
                "text": "#hiring SDET - Automation (Hyderabad, Hybrid)\nWe're looking for Selenium, Java and TestNG skills. "
                        "Use subject: Application for [Role] - Your Name\nMail resume to jobs@umbrella.io"},
}
