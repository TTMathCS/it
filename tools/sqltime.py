"""Times different ways of writing the same query on large tables, on PostgreSQL and SQLite, for chapter 26.

    python3 tools/sqltime.py [files...]        run every timing and write the tables into the pages (takes minutes)
    python3 tools/sqltime.py --check [files]   only check that every <!-- timing NAME --> names a known scenario

A scenario builds its tables (the same rows on both databases, from a fixed random seed), runs ANALYZE, then runs each
version of the query: three times when it is quick (the median is shown), once when it takes more than 5 seconds,
and stops it after TIMEOUT seconds. Every version that finishes must return exactly the same rows as the first
version, on both databases, or the run fails: a fast query that gives a different answer is not an improvement.

In a page:

    <!-- timing NAME -->
    <!-- /timing -->

Times change from machine to machine and from run to run; the page says when and where they were measured, and the
ratios between versions are the point. PostgreSQL runs with parallel workers switched off, so that both databases
use one processor core and the comparison is about the query, not the hardware.
"""
import datetime, glob, os, random, re, sqlite3, statistics, sys, time

import psycopg2
from psycopg2.extras import execute_values

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PGHOST = os.environ.get("PGHOST", "localhost")
PGUSER = os.environ.get("PGUSER", "postgres")
MARK = re.compile(r"^(\s*)<!-- timing ([a-z0-9-]+) -->\s*$")
TIMEOUT = 30


def emps(n, depts):
    r = random.Random(1)
    return {"big_emps": ("emp_id INTEGER PRIMARY KEY, dept_id INTEGER NOT NULL, salary INTEGER NOT NULL",
                         [(i, r.randint(1, depts), r.randint(40000, 160000)) for i in range(1, n + 1)])}


def visits(n, customers):
    """n (customer, day) pairs, unique, so that 'previous day' has one answer."""
    r = random.Random(2)
    per = n // customers
    rows, i = [], 0
    for c in range(1, customers + 1):
        for d in sorted(r.sample(range(1, per * 3), per)):
            i += 1
            rows.append((i, c, d))
    return {"visits": ("visit_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, day INTEGER NOT NULL", rows)}


def shop(customers, orders):
    r = random.Random(3)
    buyers = [i for i in range(1, customers + 1) if i % 5]  # customers 5, 10, 15 ... never order
    return {
        "c": ("customer_id INTEGER PRIMARY KEY, name VARCHAR(20) NOT NULL",
              [(i, f"customer {i}") for i in range(1, customers + 1)]),
        "o": ("order_id INTEGER PRIMARY KEY, customer_id INTEGER, amount INTEGER NOT NULL",
              # a few orders have no customer (NULL)
              [(i, None if i % 997 == 0 else r.choice(buyers), r.randint(1, 100000))
               for i in range(1, orders + 1)]),
    }


ABOVE_AVG = {
    "correlated subquery": """SELECT e.emp_id FROM big_emps e
        WHERE e.salary > (SELECT AVG(x.salary) FROM big_emps x WHERE x.dept_id = e.dept_id) ORDER BY e.emp_id""",
    "window function": """SELECT emp_id FROM (SELECT emp_id, salary, AVG(salary) OVER (PARTITION BY dept_id) AS dept_avg
        FROM big_emps) t WHERE salary > dept_avg ORDER BY emp_id""",
    "join to a grouped CTE": """WITH d AS (SELECT dept_id, AVG(salary) AS dept_avg FROM big_emps GROUP BY dept_id)
        SELECT e.emp_id FROM big_emps e JOIN d ON d.dept_id = e.dept_id WHERE e.salary > d.dept_avg ORDER BY e.emp_id""",
}
PREVIOUS = {
    "self join on earlier days": """SELECT a.visit_id, MAX(b.day) AS previous_day FROM visits a
        LEFT JOIN visits b ON b.customer_id = a.customer_id AND b.day < a.day
        GROUP BY a.visit_id ORDER BY a.visit_id""",
    "LAG window function": """SELECT visit_id, LAG(day) OVER (PARTITION BY customer_id ORDER BY day) AS previous_day
        FROM visits ORDER BY visit_id""",
}
ANTI = {
    "NOT IN": "SELECT customer_id FROM c WHERE customer_id NOT IN (SELECT customer_id FROM o WHERE customer_id IS NOT NULL) ORDER BY customer_id",
    "NOT EXISTS": "SELECT customer_id FROM c WHERE NOT EXISTS (SELECT 1 FROM o WHERE o.customer_id = c.customer_id) ORDER BY customer_id",
    "LEFT JOIN ... IS NULL": "SELECT c.customer_id FROM c LEFT JOIN o ON o.customer_id = c.customer_id WHERE o.order_id IS NULL ORDER BY c.customer_id",
}
TOP1 = {
    "ROW_NUMBER, keep 1": """SELECT customer_id, amount FROM (SELECT customer_id, amount,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY amount DESC, order_id) AS rn FROM o WHERE customer_id IS NOT NULL) t
        WHERE rn = 1 ORDER BY customer_id""",
    "GROUP BY MAX": """SELECT customer_id, MAX(amount) AS amount FROM o WHERE customer_id IS NOT NULL
        GROUP BY customer_id ORDER BY customer_id""",
    "correlated = (SELECT MAX ...)": """SELECT DISTINCT o.customer_id, o.amount FROM o
        WHERE o.customer_id IS NOT NULL AND o.amount = (SELECT MAX(x.amount) FROM o x WHERE x.customer_id = o.customer_id)
        ORDER BY o.customer_id""",
}
LOOKUP = {
    "no index": "SELECT order_id, amount FROM o WHERE customer_id = 4321 ORDER BY order_id",
    "with an index on customer_id": "SELECT order_id, amount FROM o WHERE customer_id = 4321 ORDER BY order_id",
}
# the two halves cannot overlap (order_id is the key), so both give the same rows
UNIONS = {
    "UNION": """SELECT COUNT(*) AS n FROM (SELECT order_id, amount FROM o WHERE amount <= 50000
        UNION SELECT order_id, amount FROM o WHERE amount > 50000) u""",
    "UNION ALL": """SELECT COUNT(*) AS n FROM (SELECT order_id, amount FROM o WHERE amount <= 50000
        UNION ALL SELECT order_id, amount FROM o WHERE amount > 50000) u""",
}

# name: list of (rows label, tables, {label: sql}, extra setup statements run before the versions named in 'before')
SCENARIOS = {
    "above-average": [("10,000 employees, 10 departments", emps(10000, 10), ABOVE_AVG, {}),
                      ("100,000 employees, 10 departments", emps(100000, 10), ABOVE_AVG, {})],
    "above-average-index": [("100,000 employees, 10 departments, index on dept_id", emps(100000, 10), ABOVE_AVG,
                             {"*": "CREATE INDEX big_emps_dept ON big_emps (dept_id)"}),
                            ("100,000 employees, 10,000 departments, index on dept_id", emps(100000, 10000), ABOVE_AVG,
                             {"*": "CREATE INDEX big_emps_dept ON big_emps (dept_id)"})],
    "previous-visit": [("100,000 visits, 10 per customer", visits(100000, 10000), PREVIOUS, {}),
                       ("100,000 visits, 1,000 per customer", visits(100000, 100), PREVIOUS, {})],
    "anti-join": [("50,000 customers, 200,000 orders, no index on o.customer_id", shop(50000, 200000), ANTI, {}),
                  ("the same, with an index on o.customer_id", shop(50000, 200000), ANTI,
                   {"*": "CREATE INDEX o_customer ON o (customer_id)"}),
                  ("the same, no index, PostgreSQL given only 64 kB of work_mem", shop(50000, 200000), ANTI,
                   {"pg*": "SET work_mem = '64kB'"})],
    "top-per-group": [("50,000 customers, 200,000 orders", shop(50000, 200000), TOP1, {})],
    "index-lookup": [("50,000 customers, 200,000 orders", shop(50000, 200000), LOOKUP,
                      {"with an index on customer_id": "CREATE INDEX o_customer ON o (customer_id)"})],
    "union": [("200,000 orders split in two halves", shop(50000, 200000), UNIONS, {})],
}


class Pg:
    name = "PostgreSQL 16"

    def __init__(self):
        a = psycopg2.connect(host=PGHOST, user=PGUSER, dbname="postgres")
        a.autocommit = True
        a.cursor().execute("DROP DATABASE IF EXISTS sqltime WITH (FORCE)")
        a.cursor().execute("CREATE DATABASE sqltime")
        a.close()
        self.con = psycopg2.connect(host=PGHOST, user=PGUSER, dbname="sqltime")
        self.con.autocommit = True
        self.cur = self.con.cursor()
        self.cur.execute("SET max_parallel_workers_per_gather = 0")

    def load(self, tables):
        for t, (cols, rows) in tables.items():
            self.cur.execute(f"CREATE TABLE {t} ({cols})")
            execute_values(self.cur, f"INSERT INTO {t} VALUES %s", rows, page_size=5000)
            self.cur.execute(f"ANALYZE {t}")

    def ddl(self, sql):
        self.cur.execute(sql)
        self.cur.execute("ANALYZE")

    def run(self, sql):
        self.cur.execute(f"SET statement_timeout = {TIMEOUT * 1000}")
        t = time.perf_counter()
        try:
            self.cur.execute(sql)
            rows = self.cur.fetchall()
        except psycopg2.errors.QueryCanceled:
            return None, None
        return time.perf_counter() - t, rows

    def close(self):
        self.con.close()


class Sq:
    name = "SQLite " + ".".join(sqlite3.sqlite_version.split(".")[:2])

    def __init__(self):
        self.con = sqlite3.connect(":memory:", isolation_level=None)

    def load(self, tables):
        for t, (cols, rows) in tables.items():
            self.con.execute(f"CREATE TABLE {t} ({cols})")
            self.con.execute("BEGIN")
            self.con.executemany(f"INSERT INTO {t} VALUES ({','.join('?' * len(rows[0]))})", rows)
            self.con.execute("COMMIT")
        self.con.execute("ANALYZE")

    def ddl(self, sql):
        self.con.execute(sql)
        self.con.execute("ANALYZE")

    def run(self, sql):
        t = time.perf_counter()
        deadline = t + TIMEOUT
        self.con.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10000)
        try:
            rows = self.con.execute(sql).fetchall()
        except sqlite3.OperationalError as e:
            if "interrupted" in str(e):
                return None, None
            raise
        finally:
            self.con.set_progress_handler(None, 0)
        return time.perf_counter() - t, rows

    def close(self):
        self.con.close()


def norm(rows):
    return [tuple(round(float(v), 6) if isinstance(v, (int, float)) or type(v).__name__ == "Decimal" else v for v in r)
            for r in rows]


def fmt(sec):
    if sec is None:
        return f"stopped after {TIMEOUT} s"
    if sec < 0.001:
        return "under 1 ms"
    if sec < 1:
        return f"{sec * 1000:.0f} ms"
    return f"{sec:.1f} s"


def measure(name):
    out = []
    for label, tables, versions, extra in SCENARIOS[name]:
        times, answer = {}, {}
        for db in (Pg(), Sq()):
            try:
                db.load(tables)
                if "*" in extra:
                    db.ddl(extra["*"])
                if "pg*" in extra and isinstance(db, Pg):  # a PostgreSQL-only setting for the whole session
                    db.cur.execute(extra["pg*"])
                for v, sql in versions.items():
                    if v in extra:
                        db.ddl(extra[v])
                    sec, rows = db.run(sql)
                    if sec is not None and sec < 5:
                        runs = [sec] + [db.run(sql)[0] for _ in range(2)]
                        sec = statistics.median(runs)
                    times[(v, db.name)] = sec
                    if rows is not None:
                        r = norm(rows)
                        if "rows" not in answer:
                            answer["rows"] = r
                        elif r != answer["rows"]:
                            raise SystemExit(f"{name} / {label}: '{v}' on {db.name} returned different rows")
                print(f"  {name} / {label}: {db.name} done", file=sys.stderr)
            finally:
                db.close()
        out.append((label, versions, times, len(answer.get("rows", []))))
    return out


def render(name, results):
    pg, sq = Pg.name, Sq.name
    day = datetime.date.today()
    lines = [f'<p class="sql-tested">Timed by <code>tools/sqltime.py</code> on {day.day} {day:%B %Y}, one 2.3 GHz Xeon '
             f'core per database, tables in memory or cache; the median of three runs. Every version that finished '
             f'returned the same rows on both databases.</p>', ""]
    for label, versions, times, n in results:
        lines += [f"| {label} ({n:,} row{'' if n == 1 else 's'} in the answer) | {pg} | {sq} |", "| --- | --- | --- |"]
        for v in versions:
            lines.append(f"| {v} | {fmt(times[(v, pg)])} | {fmt(times[(v, sq)])} |")
        lines.append("")
    return lines[:-1]


def process(path, check):
    lines = open(path).read().split("\n")
    out, i, problems, count = [], 0, [], 0
    while i < len(lines):
        m = MARK.match(lines[i])
        if not m:
            out.append(lines[i]); i += 1; continue
        indent, name = m.groups()
        j = i + 1
        while j < len(lines) and lines[j].strip() != "<!-- /timing -->":
            j += 1
        if j == len(lines) or name not in SCENARIOS:
            problems.append(f"{path}:{i + 1}: unknown timing {name} or no <!-- /timing -->")
            out.append(lines[i]); i += 1; continue
        out.append(lines[i])
        if check:
            out.extend(lines[i + 1:j])
            if j == i + 1:
                problems.append(f"{path}:{i + 1}: timing {name} has never been run")
        else:
            out.extend(indent + l if l else "" for l in render(name, measure(name)))
        out.append(lines[j])
        count += 1
        i = j + 1
    if not check:
        open(path, "w").write("\n".join(out))
    return count, problems


def main():
    check = "--check" in sys.argv
    files = [a for a in sys.argv[1:] if not a.startswith("--")] or sorted(glob.glob(os.path.join(ROOT, "docs/databases/sql/*.md")))
    total, bad = 0, []
    for f in files:
        n, p = process(f, check)
        total += n
        bad += p
    for p in bad:
        print(p)
    print(f"{total} timings in {len(files)} pages, {len(bad)} problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
