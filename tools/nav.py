# Rewrites the Books menu in mkdocs.yml from the category folders in docs/ (python3 tools/nav.py).
# A category shows up once docs/<category>/index.md exists; a course once docs/<category>/<course>/index.md exists.
# Inside a course: index.md, then the ORDER list if the course has one; otherwise the FRONT pages it has (in this order), then the NN-Name.md chapters, then the
# BACK pages it has. Any other page in a course folder is left off the menu (and mkdocs warns about it).
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# (folder, menu name), in menu order. Planned 11 Nov 2026; a new category is one line here.
CATEGORIES = [
    ("tech-by-math", "Tech by Math"),
    ("databases", "Databases"),
    ("data-engineering", "Data engineering"),
    ("warehouses-bi", "Data warehouses and BI"),
    ("programming", "Programming"),
    ("cloud", "Cloud"),
    ("devops", "DevOps"),
    ("servers", "Servers and operating systems"),
    ("enterprise", "Enterprise applications"),
    ("security", "Identity and security"),
    ("operations", "Monitoring and operations"),
    ("ai-ml", "AI and machine learning"),
    ("interview", "Interview prep"),
]
# course folder -> menu name; a course not listed here is named from its folder
COURSES = {
    "sql": "SQL",
    "webassembly": "WebAssembly",
    "databricks": "Databricks and the medallion model",
    "codility": "Codility test prep",
    "postgresql": "PostgreSQL",
    "parquet": "Apache Parquet",
    "spark": "Apache Spark",
    "kafka": "Apache Kafka",
    "elasticsearch": "Elasticsearch",
    "dremio": "Dremio",
    "nifi": "Apache NiFi",
    "kubernetes": "Kubernetes",
    "git": "Git",
    "pki": "PKI and certificates",
    "network": "Computer networks",
    "ai": "AI",
    "ai-agent": "AI agents",
}
# a category whose courses are not in alphabetical order lists them here
COURSE_ORDER = {
    "tech-by-math": ["postgresql", "parquet", "spark", "kafka", "elasticsearch", "dremio", "nifi", "kubernetes", "git",
                     "pki", "network", "ai", "ai-agent"],
}
# a course whose pages are not numbered lists them here, in menu order (after its index.md)
ORDER = {
    "codility": ["your-test.md", "full-mock-a.md", "full-mock-b.md", "full-mock-c.md", "cheat-sheet.md", "how-codility-works.md", "test-day-plan.md", "mock-test-1.md", "sql-practice.md",
                 "python-practice.md", "mock-test-2.md", "mock-test-3.md", "mock-test-4.md",
                 "mock-test-5.md", "mock-test-6.md", "flash-cards.md", "asked-aloud.md",
                 "common-mistakes.md", "codility-tasks.md"],
}
FRONT = ["fast-track.md", "cheat-sheet.md", "which-technique.md", "sample-database.md"]
BACK = ["drills.md", "analytics-workshop.md", "glossary.md"]


def title(folder):
    return COURSES.get(folder, folder.replace("-", " ").capitalize())


out = ["  # books: start", "  - Books:", "      - books/index.md"]
for cat, name in CATEGORIES:
    cp = os.path.join(ROOT, "docs", cat)
    if not os.path.exists(os.path.join(cp, "index.md")):
        continue
    out += [f'      - "{name}":', f"          - {cat}/index.md"]
    courses = sorted(os.listdir(cp))
    if cat in COURSE_ORDER:
        courses = [c for c in COURSE_ORDER[cat] if c in courses] + [c for c in courses if c not in COURSE_ORDER[cat]]
    for course in courses:
        p = os.path.join(cp, course)
        if not os.path.exists(os.path.join(p, "index.md")):
            continue
        out += [f'          - "{title(course)}":', f"              - {cat}/{course}/index.md"]
        files = os.listdir(p)
        if course in ORDER:
            out += [f"              - {cat}/{course}/{f}" for f in ORDER[course] if f in files]
            continue
        out += [f"              - {cat}/{course}/{f}" for f in FRONT if f in files]
        chapters = [f for f in files if re.match(r"\d\d-.*\.md$", f)]
        # a numbered folder with its own README.md or index.md is a chapter too (the Tech by Math system courses)
        for f in files:
            if re.match(r"\d\d-", f) and os.path.isdir(os.path.join(p, f)):
                chapters += [f"{f}/{i}" for i in ("index.md", "README.md") if os.path.exists(os.path.join(p, f, i))][:1]
        out += [f"              - {cat}/{course}/{f}" for f in sorted(chapters)]
        out += [f"              - {cat}/{course}/{f}" for f in BACK if f in files]
out.append("  # books: end")

y = os.path.join(ROOT, "mkdocs.yml")
s = open(y).read()
a, b = s.index("  # books: start"), s.index("  # books: end") + len("  # books: end")
open(y, "w").write(s[:a] + "\n".join(out) + s[b:])
print(len(out) - 4, "menu lines")
