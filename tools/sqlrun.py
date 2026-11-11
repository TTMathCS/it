"""Runs every marked SQL example in the SQL course on PostgreSQL and SQLite and writes its real result under it.

    python3 tools/sqlrun.py [--check] [files...]     (default: every .md file under docs/databases/sql)

A block is marked by an HTML comment on the line before its ```sql fence (indented like the fence):

    <!-- sql -->            run on both; the results must match; the result table is written below
    <!-- sql pg -->         PostgreSQL only            <!-- sql sqlite -->   SQLite only
    <!-- sql ... error -->  must fail (on every database it runs on); the error messages are written below
    <!-- sql pgerror -->    must fail on PostgreSQL and run on SQLite (SQLite is more forgiving); both outcomes written
    <!-- sql ... quiet -->  run it, show no result (CREATE TABLE ...)
    <!-- sql ... keep -->   its changes stay for the rest of the page (otherwise each block is rolled back)
    <!-- sql ... same -->   must give the same rows as the block before it (a dialect variant in a tab)
    <!-- sql ... ordered --> compare row order too (automatic when the outermost query has ORDER BY)
    <!-- sql ... raw -->    runs outside a transaction (blocks that BEGIN / COMMIT themselves); always kept
    <!-- sql ... random --> the result may change from run to run (shown on purpose); skip the storage-order check
    <!-- sql setup -->      a task's own tables (CREATE + INSERT): kept for the rest of the page, shown as "loads on ..."
    <!-- sql ... expect --> also write this block's result table into the nearest <!-- expected --> ... <!-- /expected -->
                            above it (the "your query should return" table of a practice task, whose answer is hidden)
Every block that is rolled back is run on SQLite a second time reading tables backwards; if that changes the result,
the query depends on luck (a tie with no tie-break, a missing ORDER BY) and the run fails.

Each page starts from a fresh copy of the shop database (docs/databases/sql/shop.sql). PostgreSQL must be running on
localhost (user postgres, no password; PGHOST/PGUSER to change). With --check nothing is written and the run fails
if any result would change. Results are written between <!-- result --> and <!-- /result -->.
"""
import decimal, datetime, glob, os, re, sqlite3, sys

import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOP = os.path.join(ROOT, "docs/databases/sql/shop.sql")
PGHOST = os.environ.get("PGHOST", "localhost")
PGUSER = os.environ.get("PGUSER", "postgres")
MARK = re.compile(r"^(\s*)<!-- sql((?: [a-z]+)*) -->\s*$")
FENCE = re.compile(r"^(\s*)```sql\s*$")


def split_sql(text):
    """Split a script into statements at semicolons outside quotes and comments."""
    out, cur, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "'\"":
            j = i + 1
            while j < n:
                if text[j] == c:
                    if j + 1 < n and text[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            cur.append(text[i:j + 1]); i = j + 1; continue
        if text.startswith("--", i):
            j = text.find("\n", i); j = n if j < 0 else j
            cur.append(text[i:j]); i = j; continue
        if c == ";":
            s = "".join(cur).strip()
            if s and not all(l.strip().startswith("--") or not l.strip() for l in s.splitlines()):
                out.append(s)
            cur = []; i += 1; continue
        cur.append(c); i += 1
    s = "".join(cur).strip()
    if s and not all(l.strip().startswith("--") or not l.strip() for l in s.splitlines()):
        out.append(s)
    return out


def outer_order_by(sql):
    """True when the last statement's outermost query ends with ORDER BY (not one inside brackets)."""
    depth, flat = 0, []
    for ch in re.sub(r"'[^']*'", "''", sql):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            flat.append(ch)
    return re.search(r"\border\s+by\b", "".join(flat), re.I) is not None


def norm(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float, decimal.Decimal)):
        f = float(v)
        return round(f, 6)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat().replace("T", " ")
    return str(v)


def show(v):
    if v is None:
        return "*NULL*"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        r = repr(v)
        return r[:-2] if r.endswith(".0") else r
    if isinstance(v, datetime.datetime):
        return v.isoformat(sep=" ")
    s = str(v).replace("|", "\\|").replace("\n", " ")
    return s if s else "*(empty text)*"


class PG:
    name = "PostgreSQL 16"

    def __init__(self, page):
        self.db = "page_" + re.sub(r"\W", "_", page).lower()[:40]
        admin = psycopg2.connect(host=PGHOST, user=PGUSER, dbname="postgres")
        admin.autocommit = True
        cur = admin.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname='shop_template'")
        if not cur.fetchone():
            cur.execute("CREATE DATABASE shop_template")
            t = psycopg2.connect(host=PGHOST, user=PGUSER, dbname="shop_template")
            t.cursor().execute(open(SHOP).read()); t.commit(); t.close()
        cur.execute(f"DROP DATABASE IF EXISTS {self.db}")
        cur.execute(f"CREATE DATABASE {self.db} TEMPLATE shop_template")
        admin.close()
        self.con = psycopg2.connect(host=PGHOST, user=PGUSER, dbname=self.db)

    def run(self, sql, keep, raw):
        con = self.con
        con.autocommit = raw
        cur = con.cursor()
        try:
            cols, rows = None, None
            for st in split_sql(sql):
                cur.execute(st)
                if cur.description:
                    cols, rows = [d[0] for d in cur.description], cur.fetchall()
                else:
                    cols, rows = None, cur.rowcount
            if not raw:
                (con.commit if keep else con.rollback)()
            return ("ok", cols, rows)
        except psycopg2.Error as e:
            if not raw:
                con.rollback()
            msg = (e.pgerror or str(e)).strip().splitlines()[0]
            return ("error", None, re.sub(r"^ERROR:\s*", "", msg))

    def close(self):
        self.con.close()
        admin = psycopg2.connect(host=PGHOST, user=PGUSER, dbname="postgres")
        admin.autocommit = True
        admin.cursor().execute(f"DROP DATABASE IF EXISTS {self.db}")
        admin.close()


class SQ:
    name = "SQLite " + ".".join(sqlite3.sqlite_version.split(".")[:2])

    def __init__(self, page):
        self.con = sqlite3.connect(":memory:", isolation_level=None)
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(open(SHOP).read())

    def run(self, sql, keep, raw):
        cur = self.con.cursor()
        if not raw:
            cur.execute("BEGIN")
        try:
            cols, rows = None, None
            for st in split_sql(sql):
                cur.execute(st)
                if cur.description:
                    cols, rows = [d[0] for d in cur.description], cur.fetchall()
                else:
                    cols, rows = None, cur.rowcount
            if not raw:
                cur.execute("COMMIT" if keep else "ROLLBACK")
            return ("ok", cols, rows)
        except sqlite3.Error as e:
            if not raw and self.con.in_transaction:
                cur.execute("ROLLBACK")
            return ("error", None, str(e))

    def close(self):
        self.con.close()


def same(a, b, ordered):
    if a[0] != b[0]:
        return False
    if a[0] == "error":
        return True
    if a[1] is None or b[1] is None:
        return a[1] == b[1]
    if [c.lower() for c in a[1]] != [c.lower() for c in b[1]]:
        return False
    ra = [tuple(norm(v) for v in r) for r in a[2]]
    rb = [tuple(norm(v) for v in r) for r in b[2]]
    if ordered:
        return ra == rb
    key = lambda r: tuple((x is None, str(type(x)), x if x is not None else 0) for x in r)
    return sorted(ra, key=key) == sorted(rb, key=key)


def table(res):
    cols, rows = res[1], res[2]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(" --- " for _ in cols) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(show(v) for v in r) + " |")
    if not rows:
        lines.append("| *(no rows)* |" + " |" * (len(cols) - 1))
    return lines


def render(results, flags, compared):
    """The lines that go between the result marks."""
    names = [db.name for db, _ in results]
    if "error" in flags or "pgerror" in flags:
        out = []
        for db, r in results:
            if r[0] == "error":
                out.append(f"<p class=\"sql-tested sql-error\">{db.name}: error: <code>{html(r[2])}</code></p>")
            else:
                n = len(r[2]) if isinstance(r[2], list) else 0
                out.append(f"<p class=\"sql-tested sql-noerror\">{db.name}: no error, it runs and returns {n} row{'s' if n != 1 else ''}.</p>")
        return out
    first = results[0][1]
    if "setup" in flags:
        return [f"<p class=\"sql-tested\">These tables load on {' and '.join(names)}.</p>"]
    if "quiet" in flags and first[1] is not None:
        n = len(first[2])
        both = ": same rows on both" if len(results) > 1 else ""
        return [f"<p class=\"sql-tested\">Ran on {' and '.join(names)}{both} ({n} row{'s' if n != 1 else ''}).</p>"]
    if "quiet" in flags or first[1] is None:
        n = first[2]
        what = f"{n} row{'s' if n != 1 else ''} changed" if isinstance(n, int) and n >= 0 else "done"
        return [f"<p class=\"sql-tested\">Ran on {' and '.join(names)}: {what}.</p>"]
    note = f"Ran on {' and '.join(names)}" + (": same rows on both." if len(results) > 1 else ".")
    if compared:
        note = f"Ran on {' and '.join(names)}: same rows as the other version."
    n = len(first[2])
    head = f"<p class=\"sql-tested\">{note} {n} row{'s' if n != 1 else ''}.</p>"
    return [head, ""] + table(first)


def html(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def process(path, check):
    lines = open(path).read().split("\n")
    page = os.path.splitext(os.path.basename(path))[0]
    dbs, out, i, problems, prev, count = None, [], 0, [], None, 0
    while i < len(lines):
        m = MARK.match(lines[i])
        if not m:
            out.append(lines[i]); i += 1; continue
        indent, flags = m.group(1), set(m.group(2).split())
        out.append(lines[i]); i += 1
        f = FENCE.match(lines[i]) if i < len(lines) else None
        if not f:
            problems.append(f"{path}:{i}: <!-- sql --> not followed by ```sql")
            continue
        j = i + 1
        while j < len(lines) and lines[j].strip() != "```":
            j += 1
        body = "\n".join(l[len(indent):] if l.startswith(indent) else l.lstrip() for l in lines[i + 1:j])
        out.extend(lines[i:j + 1]); i = j + 1
        # skip an old result
        k = i
        while k < len(lines) and lines[k].strip() == "":
            k += 1
        if k < len(lines) and lines[k].strip() == "<!-- result -->":
            e = k
            while e < len(lines) and lines[e].strip() != "<!-- /result -->":
                e += 1
            old = lines[k:e + 1]
            i = e + 1
        else:
            old = None
        if dbs is None:
            dbs = {"pg": PG(page), "sqlite": SQ(page)}
        use = [d for d in ("pg", "sqlite") if d in flags] or ["pg", "sqlite"]
        keep, raw = "keep" in flags or "setup" in flags, "raw" in flags
        results = [(dbs[d], dbs[d].run(body, keep or raw, raw)) for d in use]
        count += 1
        where = f"{path}:{i}"
        ordered = "ordered" in flags or outer_order_by(body)
        # a result must not depend on the order rows happen to be stored in: SQLite can read tables backwards
        # (PRAGMA reverse_unordered_selects); run again that way and compare
        if "sqlite" in use and not (keep or raw) and "random" not in flags:
            sq = dbs["sqlite"]
            sq.con.execute("PRAGMA reverse_unordered_selects = ON")
            again = sq.run(body, False, False)
            sq.con.execute("PRAGMA reverse_unordered_selects = OFF")
            first = dict((d, r) for d, (db, r) in zip(use, results))["sqlite"]
            if not same(first, again, ordered):
                problems.append(f"{where}: the result depends on row storage order (ties without a tie-break?):\n  normal   {fmt(first)}\n  reversed {fmt(again)}")
        for db, r in results:
            want = "error" in flags or ("pgerror" in flags and db.name.startswith("PostgreSQL"))
            if want != (r[0] == "error"):
                problems.append(f"{where}: {db.name}: " + (f"expected an error, got rows" if "error" in flags else f"error: {r[2]}"))
        if len(results) == 2 and "pgerror" not in flags and not same(results[0][1], results[1][1], ordered):
            problems.append(f"{where}: PostgreSQL and SQLite differ:\n  pg     {fmt(results[0][1])}\n  sqlite {fmt(results[1][1])}")
        compared = False
        if "same" in flags:
            compared = True
            if prev is None or not same(prev, results[0][1], ordered):
                problems.append(f"{where}: 'same' block differs from the block before it:\n  before {fmt(prev)}\n  this   {fmt(results[0][1])}")
        prev = results[0][1]
        if "expect" in flags and results[0][1][0] == "ok" and results[0][1][1] is not None:
            a = max((n for n, l in enumerate(out) if l.strip() == "<!-- expected -->"), default=None)
            b = next((n for n in range(a, len(out)) if out[n].strip() == "<!-- /expected -->"), None) if a is not None else None
            if b is None:
                problems.append(f"{where}: 'expect' block with no <!-- expected --> ... <!-- /expected --> above it")
            else:
                ind = out[a][:len(out[a]) - len(out[a].lstrip())]
                want = [ind + l for l in table(results[0][1])]
                if [l.rstrip() for l in out[a + 1:b]] != [l.rstrip() for l in want] and check:
                    problems.append(f"{where}: expected table changed")
                out[a + 1:b] = want
        new = [indent + "<!-- result -->"] + [(indent + l) if l else "" for l in render(results, flags, compared)] + [indent + "<!-- /result -->"]
        out.append("")
        out.extend(new)
        if old is not None and [l.rstrip() for l in old] != [l.rstrip() for l in new]:
            problems.append(f"{where}: result changed") if check else None
        elif old is None and check:
            problems.append(f"{where}: result missing")
        # keep one blank line after the result
        if i < len(lines) and lines[i].strip() != "":
            out.append("")
    if dbs:
        for d in dbs.values():
            d.close()
    text = "\n".join(out)
    text = re.sub(r"\n{3,}(\s*<!-- result -->)", r"\n\n\1", text)
    if not check:
        open(path, "w").write(text)
    return count, problems


def fmt(r):
    if r is None:
        return "None"
    if r[0] == "error":
        return "ERROR " + r[2]
    if r[1] is None:
        return f"(no rows, {r[2]} changed)"
    return f"{r[1]} {[tuple(norm(v) for v in row) for row in r[2]][:8]}{' ...' if len(r[2]) > 8 else ''}"


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
    print(f"{total} SQL blocks in {len(files)} pages, {len(bad)} problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
