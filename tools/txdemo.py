"""Runs the two-session transaction timelines in the SQL course and writes what really happened into the pages.

    python3 tools/txdemo.py [--check] [files...]     (default: every .md file under docs/databases/sql)

sqlrun.py runs one statement list on one connection. Transactions need two people at once, so this tool opens two
connections (session A and session B) to the same database and runs a scenario step by step, in the order written.
A step can be started "in the background": if it is still waiting after a moment (blocked by the other session's
lock), the timeline says so and shows its result later, at its "join" step.

In a page, a scenario is placed with

    <!-- txdemo NAME DB -->            DB is pg or sqlite
    <!-- /txdemo -->

and everything between the two lines is replaced by the timeline. With --check nothing is written and the run fails if
any timeline would change. PostgreSQL must be running on localhost (user postgres, no password); SQLite uses a
temporary file, because two connections to an in-memory database would be two different databases.
"""
import glob, os, re, sqlite3, sys, tempfile, threading, time

import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PGHOST = os.environ.get("PGHOST", "localhost")
PGUSER = os.environ.get("PGUSER", "postgres")
MARK = re.compile(r"^(\s*)<!-- txdemo ([a-z0-9-]+) (pg|sqlite) -->\s*$")

ACCOUNTS = [
    "CREATE TABLE accounts (id INTEGER PRIMARY KEY, owner VARCHAR(20) NOT NULL, balance INTEGER NOT NULL CHECK (balance >= 0))",
    "INSERT INTO accounts VALUES (1, 'Ana', 300), (2, 'Ben', 100)",
]
DOCTORS = [
    "CREATE TABLE doctors (name VARCHAR(20) PRIMARY KEY, on_call INTEGER NOT NULL)",
    "INSERT INTO doctors VALUES ('Kim', 1), ('Lee', 1)",
]
FLIGHT = [
    "CREATE TABLE flights (id INTEGER PRIMARY KEY, seats INTEGER NOT NULL, seats_left INTEGER NOT NULL CHECK (seats_left >= 0))",
    "CREATE TABLE bookings (flight_id INTEGER NOT NULL, passenger VARCHAR(20) NOT NULL)",
    "INSERT INTO flights VALUES (1, 2, 1)",
    "INSERT INTO bookings VALUES (1, 'Cai')",
]
COUNT_BOOKED = "SELECT COUNT(*) AS booked FROM bookings WHERE flight_id = 1"
BOTH = "SELECT owner, balance FROM accounts ORDER BY id"

# each step: (session, sql) or (session, sql, "bg") or (session, "join")
SCENARIOS = {
    # an error in the middle of a transaction, then COMMIT
    "atomic": (ACCOUNTS, [
        ("A", "BEGIN"),
        ("A", "UPDATE accounts SET balance = balance + 500 WHERE id = 2"),
        ("A", "UPDATE accounts SET balance = balance - 500 WHERE id = 1"),
        ("A", BOTH),
        ("A", "COMMIT"),
        ("A", BOTH),
    ]),
    # the safe way on every database: ROLLBACK when a statement fails
    "atomic-rollback": (ACCOUNTS, [
        ("A", "BEGIN"),
        ("A", "UPDATE accounts SET balance = balance + 500 WHERE id = 2"),
        ("A", "UPDATE accounts SET balance = balance - 500 WHERE id = 1"),
        ("A", "ROLLBACK"),
        ("A", BOTH),
    ]),
    # nobody sees uncommitted changes, not even at READ UNCOMMITTED
    "dirty": (ACCOUNTS, [
        ("A", "BEGIN"),
        ("A", "UPDATE accounts SET balance = 0 WHERE id = 1"),
        ("B", "BEGIN ISOLATION LEVEL READ UNCOMMITTED"),
        ("B", "SELECT balance FROM accounts WHERE id = 1"),
        ("A", "COMMIT"),
        ("B", "SELECT balance FROM accounts WHERE id = 1"),
        ("B", "COMMIT"),
    ]),
    # READ COMMITTED: the same SELECT twice in one transaction can give two answers
    "nonrepeatable": (ACCOUNTS, [
        ("A", "BEGIN"),
        ("A", "SELECT balance FROM accounts WHERE id = 1"),
        ("B", "UPDATE accounts SET balance = 250 WHERE id = 1"),
        ("A", "SELECT balance FROM accounts WHERE id = 1"),
        ("A", "SELECT COUNT(*) AS accounts FROM accounts"),
        ("B", "INSERT INTO accounts VALUES (3, 'Cy', 40)"),
        ("A", "SELECT COUNT(*) AS accounts FROM accounts"),
        ("A", "COMMIT"),
    ]),
    # REPEATABLE READ: one snapshot for the whole transaction
    "repeatable": (ACCOUNTS, [
        ("A", "BEGIN ISOLATION LEVEL REPEATABLE READ"),
        ("A", "SELECT balance FROM accounts WHERE id = 1"),
        ("B", "UPDATE accounts SET balance = 250 WHERE id = 1"),
        ("A", "SELECT balance FROM accounts WHERE id = 1"),
        ("A", "SELECT COUNT(*) AS accounts FROM accounts"),
        ("B", "INSERT INTO accounts VALUES (3, 'Cy', 40)"),
        ("A", "SELECT COUNT(*) AS accounts FROM accounts"),
        ("A", "COMMIT"),
        ("A", "SELECT balance FROM accounts WHERE id = 1"),
    ]),
    # read, compute in the program, write back: one deposit disappears
    "lost-update": (ACCOUNTS, [
        ("A", "BEGIN"),
        ("A", "SELECT balance FROM accounts WHERE id = 1"),
        ("B", "BEGIN"),
        ("B", "SELECT balance FROM accounts WHERE id = 1"),
        ("A", "UPDATE accounts SET balance = 350 WHERE id = 1"),
        ("A", "COMMIT"),
        ("B", "UPDATE accounts SET balance = 320 WHERE id = 1"),
        ("B", "COMMIT"),
        ("A", "SELECT balance FROM accounts WHERE id = 1"),
    ]),
    # fix 1: let the database do the arithmetic; the second writer waits, then adds to the new value
    "relative-update": (ACCOUNTS, [
        ("A", "BEGIN"),
        ("A", "UPDATE accounts SET balance = balance + 50 WHERE id = 1"),
        ("B", "UPDATE accounts SET balance = balance + 20 WHERE id = 1", "bg"),
        ("A", "COMMIT"),
        ("B", "join"),
        ("A", "SELECT balance FROM accounts WHERE id = 1"),
    ]),
    # fix 2: lock the row when you read it
    "for-update": (ACCOUNTS, [
        ("A", "BEGIN"),
        ("A", "SELECT balance FROM accounts WHERE id = 1 FOR UPDATE"),
        ("B", "BEGIN"),
        ("B", "SELECT balance FROM accounts WHERE id = 1 FOR UPDATE", "bg"),
        ("A", "UPDATE accounts SET balance = 350 WHERE id = 1"),
        ("A", "COMMIT"),
        ("B", "join"),
        ("B", "UPDATE accounts SET balance = 370 WHERE id = 1"),
        ("B", "COMMIT"),
        ("A", "SELECT balance FROM accounts WHERE id = 1"),
    ]),
    # fix 3: REPEATABLE READ refuses the second write
    "rr-conflict": (ACCOUNTS, [
        ("A", "BEGIN ISOLATION LEVEL REPEATABLE READ"),
        ("A", "SELECT balance FROM accounts WHERE id = 1"),
        ("B", "BEGIN ISOLATION LEVEL REPEATABLE READ"),
        ("B", "SELECT balance FROM accounts WHERE id = 1"),
        ("A", "UPDATE accounts SET balance = 350 WHERE id = 1"),
        ("A", "COMMIT"),
        ("B", "UPDATE accounts SET balance = 320 WHERE id = 1"),
        ("B", "ROLLBACK"),
        ("A", "SELECT balance FROM accounts WHERE id = 1"),
    ]),
    # write skew: each checks "someone else is on call", each goes off call
    "skew-rr": (DOCTORS, [
        ("A", "BEGIN ISOLATION LEVEL REPEATABLE READ"),
        ("B", "BEGIN ISOLATION LEVEL REPEATABLE READ"),
        ("A", "SELECT SUM(on_call) AS on_call FROM doctors"),
        ("B", "SELECT SUM(on_call) AS on_call FROM doctors"),
        ("A", "UPDATE doctors SET on_call = 0 WHERE name = 'Kim'"),
        ("B", "UPDATE doctors SET on_call = 0 WHERE name = 'Lee'"),
        ("A", "COMMIT"),
        ("B", "COMMIT"),
        ("A", "SELECT SUM(on_call) AS on_call FROM doctors"),
    ]),
    "skew-serializable": (DOCTORS, [
        ("A", "BEGIN ISOLATION LEVEL SERIALIZABLE"),
        ("B", "BEGIN ISOLATION LEVEL SERIALIZABLE"),
        ("A", "SELECT SUM(on_call) AS on_call FROM doctors"),
        ("B", "SELECT SUM(on_call) AS on_call FROM doctors"),
        ("A", "UPDATE doctors SET on_call = 0 WHERE name = 'Kim'"),
        ("B", "UPDATE doctors SET on_call = 0 WHERE name = 'Lee'"),
        ("A", "COMMIT"),
        ("B", "COMMIT"),
        ("A", "SELECT SUM(on_call) AS on_call FROM doctors"),
    ]),
    # Tech by Math tutorial 4: the last seat. Each checks "1 booked of 2 seats", each books: 3 bookings for 2 seats
    "seat-rc": (FLIGHT, [
        ("A", "BEGIN"),
        ("B", "BEGIN"),
        ("A", COUNT_BOOKED),
        ("B", COUNT_BOOKED),
        ("A", "INSERT INTO bookings VALUES (1, 'Ana')"),
        ("B", "INSERT INTO bookings VALUES (1, 'Ben')"),
        ("A", "COMMIT"),
        ("B", "COMMIT"),
        ("A", COUNT_BOOKED),
    ]),
    "seat-rr": (FLIGHT, [
        ("A", "BEGIN ISOLATION LEVEL REPEATABLE READ"),
        ("B", "BEGIN ISOLATION LEVEL REPEATABLE READ"),
        ("A", COUNT_BOOKED),
        ("B", COUNT_BOOKED),
        ("A", "INSERT INTO bookings VALUES (1, 'Ana')"),
        ("B", "INSERT INTO bookings VALUES (1, 'Ben')"),
        ("A", "COMMIT"),
        ("B", "COMMIT"),
        ("A", COUNT_BOOKED),
    ]),
    "seat-serializable": (FLIGHT, [
        ("A", "BEGIN ISOLATION LEVEL SERIALIZABLE"),
        ("B", "BEGIN ISOLATION LEVEL SERIALIZABLE"),
        ("A", COUNT_BOOKED),
        ("B", COUNT_BOOKED),
        ("A", "INSERT INTO bookings VALUES (1, 'Ana')"),
        ("B", "INSERT INTO bookings VALUES (1, 'Ben')"),
        ("A", "COMMIT"),
        ("B", "COMMIT"),
        ("A", COUNT_BOOKED),
    ]),
    # the fix by a conflict on one row: take the seat from the counter, which cannot go below 0
    "seat-counter": (FLIGHT, [
        ("A", "BEGIN"),
        ("B", "BEGIN"),
        ("A", "UPDATE flights SET seats_left = seats_left - 1 WHERE id = 1"),
        ("B", "UPDATE flights SET seats_left = seats_left - 1 WHERE id = 1", "bg"),
        ("A", "INSERT INTO bookings VALUES (1, 'Ana')"),
        ("A", "COMMIT"),
        ("B", "join"),
        ("B", "ROLLBACK"),
        ("A", COUNT_BOOKED),
    ]),
    # two sessions lock two rows in opposite order
    "deadlock": (ACCOUNTS, [
        ("A", "BEGIN"),
        ("A", "UPDATE accounts SET balance = balance - 10 WHERE id = 1"),
        ("B", "BEGIN"),
        ("B", "UPDATE accounts SET balance = balance - 10 WHERE id = 2"),
        ("A", "UPDATE accounts SET balance = balance + 10 WHERE id = 2", "bg"),
        ("B", "UPDATE accounts SET balance = balance + 10 WHERE id = 1"),
        ("A", "join"),
        ("A", "COMMIT"),
        ("B", "ROLLBACK"),
        ("A", BOTH),
    ]),
    # SQLite: one writer at a time; readers see the last committed data
    "sqlite-writer": (ACCOUNTS, [
        ("A", "BEGIN"),
        ("A", "UPDATE accounts SET balance = 0 WHERE id = 1"),
        ("B", "SELECT balance FROM accounts WHERE id = 1"),
        ("B", "UPDATE accounts SET balance = 999 WHERE id = 2"),
        ("A", "COMMIT"),
        ("B", "UPDATE accounts SET balance = 999 WHERE id = 2"),
        ("B", BOTH),
    ]),
}


class Pg:
    name = "PostgreSQL 16"

    def __init__(self, schema):
        admin = psycopg2.connect(host=PGHOST, user=PGUSER, dbname="postgres")
        admin.autocommit = True
        admin.cursor().execute("DROP DATABASE IF EXISTS txdemo WITH (FORCE)")
        admin.cursor().execute("CREATE DATABASE txdemo")
        admin.close()
        self.cons = {}
        for s in "AB":
            c = psycopg2.connect(host=PGHOST, user=PGUSER, dbname="txdemo")
            c.autocommit = True
            self.cons[s] = c
        for st in schema:
            self.cons["A"].cursor().execute(st)

    def run(self, s, sql):
        cur = self.cons[s].cursor()
        try:
            cur.execute(sql)
            if cur.description:
                return ("rows", [d[0] for d in cur.description], cur.fetchall())
            return ("ok", cur.statusmessage)
        except psycopg2.Error as e:
            return ("error", (e.pgerror or str(e)).strip().splitlines()[0].replace("ERROR:", "").strip())

    def close(self):
        for c in self.cons.values():
            c.close()


class Sq:
    name = "SQLite " + ".".join(sqlite3.sqlite_version.split(".")[:2])

    def __init__(self, schema):
        self.dir = tempfile.TemporaryDirectory()
        path = os.path.join(self.dir.name, "txdemo.db")
        self.cons = {s: sqlite3.connect(path, isolation_level=None, timeout=0, check_same_thread=False) for s in "AB"}
        for st in schema:
            self.cons["A"].execute(st)

    def run(self, s, sql):
        cur = self.cons[s].cursor()
        try:
            cur.execute(sql)
            if cur.description:
                return ("rows", [d[0] for d in cur.description], cur.fetchall())
            word = sql.split()[0].upper()
            return ("ok", f"{word} {cur.rowcount}" if word in ("INSERT", "UPDATE", "DELETE") else word)
        except sqlite3.Error as e:
            return ("error", str(e))

    def close(self):
        for c in self.cons.values():
            c.close()
        self.dir.cleanup()


def show(r):
    if r[0] == "error":
        return "**error:** " + code(r[1])
    if r[0] == "ok":
        return code(r[1])
    cols, rows = r[1], r[2]
    if not rows:
        return "no rows"
    if len(cols) == 1:
        return f"{cols[0]} = " + ", ".join(str(row[0]) for row in rows)
    return "; ".join(", ".join(str(v) for v in row) for row in rows)


def code(s):
    return "<code>" + str(s).replace("&", "&amp;").replace("<", "&lt;").replace("|", "&#124;") + "</code>"


def timeline(name, db):
    schema, steps = SCENARIOS[name]
    con = (Pg if db == "pg" else Sq)(schema)
    rows, waiting = [], {}
    try:
        for n, step in enumerate(steps, 1):
            s = step[0]
            if step[1] == "join":
                t, box, row = waiting.pop(s)
                t.join(30)
                if t.is_alive():
                    raise RuntimeError(f"{name}: session {s} still waiting after 30 s")
                rows.append((n, s, "*(its waiting statement finishes)*", show(box[0])))
                continue
            sql = step[1]
            if len(step) > 2 and step[2] == "bg":
                box = []
                t = threading.Thread(target=lambda: box.append(con.run(s, sql)), daemon=True)
                t.start()
                t.join(1.5)
                waiting[s] = (t, box, len(rows))
                if t.is_alive():
                    rows.append((n, s, code(sql), "*waits: the row is locked by the other session*"))
                else:
                    rows.append((n, s, code(sql), show(box[0]) + " *(did not wait)*"))
                continue
            rows.append((n, s, code(sql), show(con.run(s, sql))))
        if waiting:
            raise RuntimeError(f"{name}: a background step was never joined")
    finally:
        con.close()
    out = [f'<p class="sql-tested">Run by <code>tools/txdemo.py</code> on {con.name}, two connections, in this order.</p>', "",
           "| # | Session A | Session B | Result |", "| --- | --- | --- | --- |"]
    for n, s, sql, res in rows:
        a, b = (sql, "") if s == "A" else ("", sql)
        out.append(f"| {n} | {a} | {b} | {res} |")
    return out


def process(path, check):
    lines = open(path).read().split("\n")
    out, i, problems, count = [], 0, [], 0
    while i < len(lines):
        m = MARK.match(lines[i])
        if not m:
            out.append(lines[i]); i += 1; continue
        indent, name, db = m.groups()
        out.append(lines[i])
        j = i + 1
        while j < len(lines) and lines[j].strip() != "<!-- /txdemo -->":
            j += 1
        if j == len(lines):
            problems.append(f"{path}:{i + 1}: no <!-- /txdemo --> after it"); break
        if name not in SCENARIOS:
            problems.append(f"{path}:{i + 1}: unknown scenario {name}"); out.extend(lines[i + 1:j + 1]); i = j + 1; continue
        new = [indent + l if l else "" for l in timeline(name, db)]
        old = lines[i + 1:j]
        if check and [l.rstrip() for l in old] != [l.rstrip() for l in new]:
            problems.append(f"{path}:{i + 1}: timeline {name} {db} changed")
        out.extend(new)
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
    print(f"{total} timelines in {len(files)} pages, {len(bad)} problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
