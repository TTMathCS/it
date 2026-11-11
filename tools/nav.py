# Rewrites the Books menu in mkdocs.yml from the category folders in docs/ (python3 tools/nav.py).
# A category shows up once docs/<category>/index.md exists; a course once docs/<category>/<course>/index.md exists.
# Inside a course: index.md, then the FRONT pages it has (in this order), then the NN-Name.md chapters, then the
# BACK pages it has. Any other page in a course folder is left off the menu (and mkdocs warns about it).
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# (folder, menu name), in menu order. Planned 11 Nov 2026; a new category is one line here.
CATEGORIES = [
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
    "databricks": "Databricks and the medallion model",
    "codility": "Codility",
}
FRONT = ["fast-track.md", "cheat-sheet.md", "sample-database.md"]
BACK = ["glossary.md"]


def title(folder):
    return COURSES.get(folder, folder.replace("-", " ").capitalize())


out = ["  # books: start", "  - Books:", "      - books/index.md"]
for cat, name in CATEGORIES:
    cp = os.path.join(ROOT, "docs", cat)
    if not os.path.exists(os.path.join(cp, "index.md")):
        continue
    out += [f'      - "{name}":', f"          - {cat}/index.md"]
    for course in sorted(os.listdir(cp)):
        p = os.path.join(cp, course)
        if not os.path.exists(os.path.join(p, "index.md")):
            continue
        out += [f'          - "{title(course)}":', f"              - {cat}/{course}/index.md"]
        files = os.listdir(p)
        out += [f"              - {cat}/{course}/{f}" for f in FRONT if f in files]
        out += [f"              - {cat}/{course}/{f}" for f in sorted(files) if re.match(r"\d\d-.*\.md$", f)]
        out += [f"              - {cat}/{course}/{f}" for f in BACK if f in files]
out.append("  # books: end")

y = os.path.join(ROOT, "mkdocs.yml")
s = open(y).read()
a, b = s.index("  # books: start"), s.index("  # books: end") + len("  # books: end")
open(y, "w").write(s[:a] + "\n".join(out) + s[b:])
print(len(out) - 4, "menu lines")
