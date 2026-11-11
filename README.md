# IT

IT courses by category: https://it.akadian.ca/ (part of Mars – your new home, www.akadian.ca). Built with MkDocs
Material in the same look as the other school sites (astronomy, networks, cs ...); GitHub Pages publishes it on every
push to `main` (`.github/workflows/pages.yml`), so a push here is a publish. Started 11 Nov 2026 (Jim: "complete SQL
course from beginner to expert ... new domain it.akadian.ca ... database -> sql ... 130+ IT systems").

## Layout

```
mkdocs.yml                    the site and its menu (the Books part is written by tools/nav.py)
docs/index.md                 the first page;  docs/start/  how the site works;  docs/books/  all courses
docs/<category>/index.md      one folder per category (databases, data-engineering, interview ...)
docs/<category>/<course>/     one folder per course: index.md, chapters NN-Name.md, optional front pages
docs/databases/sql/shop.sql   the sample database every SQL example runs on
docs/javascripts/, stylesheets/  the shared reader files (same as the other school sites) and it.css
tools/nav.py                  rewrites the Books menu from the folders; the category list is at its top
tools/sqlrun.py               runs every marked SQL example on PostgreSQL and SQLite and writes the real result
tools/txdemo.py               runs the two-session transaction timelines (chapter 20) and writes what happened
```

## Categories

databases, data-engineering, warehouses-bi, programming, cloud, devops, servers, enterprise, security, operations,
ai-ml, interview. A new category is one line in `tools/nav.py`; it joins the menu once `docs/<category>/index.md`
exists.

## Writing SQL examples

Put `<!-- sql -->` on the line before a ```` ```sql ```` block (flags: `pg`, `sqlite`, `error`, `pgerror`, `quiet`,
`keep`, `same`, `ordered`, `raw`, `random`, `setup`, `expect`; see the top of `tools/sqlrun.py`). A two-session
timeline is `<!-- txdemo NAME pg -->` ... `<!-- /txdemo -->`, with the scenario NAME defined in `tools/txdemo.py`. Then, with PostgreSQL running locally:

```
python3 tools/sqlrun.py            # run every example and write its result
python3 tools/sqlrun.py --check    # fail if any result would change or the two databases disagree
python3 tools/txdemo.py --check    # the same for the transaction timelines
python3 tools/nav.py
mkdocs build --strict
```

Never type a result table by hand; the tool writes them.
