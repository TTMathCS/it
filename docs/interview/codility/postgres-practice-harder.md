# PostgreSQL practice: harder patterns

Eight harder PostgreSQL tasks: streaks across month ends, sessions, percent change with NULLIF, median and 90th percentile with percentile_cont, a pivot with FILTER, a recursive referral chain, an anti-join three ways, and overlapping shifts. Every solution was run on PostgreSQL 16 with the example and gave exactly the expected result. They have not had random or large-table tests, so write your own edge cases before you open a solution.

### 1. Login streaks across month ends

**Topic:** gaps and islands on dates

`logins` has one row per login. A user may log in more than once a day. A streak is a run of calendar days in a row
with at least one login each, and it may cross the end of a month.

Return every streak of **3 days or more**: `user_id`, `streak_start`, `streak_end` and `days`. Sort by `user_id`, then
`streak_start`.

**Tables and example data**

```sql
CREATE TABLE logins (
    login_id   INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    login_date DATE NOT NULL
);
INSERT INTO logins VALUES (1, 1, '2026-01-29');
INSERT INTO logins VALUES (2, 1, '2026-01-30');
INSERT INTO logins VALUES (3, 1, '2026-01-30');
INSERT INTO logins VALUES (4, 1, '2026-01-31');
INSERT INTO logins VALUES (5, 1, '2026-02-01');
INSERT INTO logins VALUES (6, 1, '2026-02-03');
INSERT INTO logins VALUES (7, 1, '2026-02-04');
INSERT INTO logins VALUES (8, 2, '2026-02-27');
INSERT INTO logins VALUES (9, 2, '2026-02-28');
INSERT INTO logins VALUES (10, 2, '2026-03-01');
INSERT INTO logins VALUES (11, 2, '2026-03-05');
INSERT INTO logins VALUES (12, 3, '2026-03-10');
INSERT INTO logins VALUES (13, 3, '2026-03-10');
INSERT INTO logins VALUES (14, 3, '2026-03-11');
```

**Your query should return**

| user_id | streak_start | streak_end | days |
|---|---|---|---|
| 1 | 2026-01-29 | 2026-02-01 | 4 |
| 2 | 2026-02-27 | 2026-03-01 | 3 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    WITH d AS (
        SELECT DISTINCT user_id, login_date FROM logins
    ),
    g AS (
        SELECT user_id, login_date,
               login_date - (ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY login_date))::int AS grp
        FROM d
    )
    SELECT user_id, MIN(login_date) AS streak_start, MAX(login_date) AS streak_end, COUNT(*) AS days
    FROM g
    GROUP BY user_id, grp
    HAVING COUNT(*) >= 3
    ORDER BY user_id, streak_start;
    ```

    **Why it works**

    1. `DISTINCT` first: user 1 logged in twice on 30 January, and a repeated day would break the numbering.
    2. Inside one streak the date goes up by 1 and `ROW_NUMBER` goes up by 1, so `date - row_number` stays the same. That
       constant is the island's key (`grp`). A missing day makes the date jump by 2 while the row number moves by 1, so
       the key changes.
    3. In PostgreSQL `date - integer` is a date, and it knows 31 January is followed by 1 February and 28 February by 1
       March in 2026. `ROW_NUMBER` is a `bigint`, and there is no `date - bigint`, so it is cast with `::int`.
    4. `HAVING COUNT(*) >= 3` drops the short runs (user 1's 3 to 4 February, user 3's two days).

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 2. Sessions with a purchase

**Topic:** sessions with a 30-minute gap

`events` holds page views and purchases. A session is a run of one user's events where each event comes **at most
30 minutes** after the one before; a gap of more than 30 minutes starts a new session. Number each user's sessions
1, 2, ... in time order. Two events of one user never share a timestamp, but break ties by `event_id` anyway.

For every session with at least one `'buy'`, return `user_id`, `session_no`, `session_start`, `first_buy` (time of
the first buy in that session) and `minutes_to_buy` (whole minutes from session start to first buy). Sort by
`user_id`, then `session_no`.

**Tables and example data**

```sql
CREATE TABLE events (
    event_id INTEGER PRIMARY KEY,
    user_id  INTEGER NOT NULL,
    ts       TIMESTAMP NOT NULL,
    event    TEXT NOT NULL
);
INSERT INTO events VALUES (1, 1, '2026-03-01 09:00:00', 'view');
INSERT INTO events VALUES (2, 1, '2026-03-01 09:10:00', 'view');
INSERT INTO events VALUES (3, 1, '2026-03-01 09:40:00', 'view');
INSERT INTO events VALUES (4, 1, '2026-03-01 09:52:00', 'buy');
INSERT INTO events VALUES (5, 1, '2026-03-01 10:23:00', 'view');
INSERT INTO events VALUES (6, 1, '2026-03-01 10:30:00', 'buy');
INSERT INTO events VALUES (7, 1, '2026-03-01 10:35:00', 'buy');
INSERT INTO events VALUES (8, 2, '2026-03-01 23:50:00', 'view');
INSERT INTO events VALUES (9, 2, '2026-03-02 00:15:00', 'buy');
INSERT INTO events VALUES (10, 2, '2026-03-02 08:00:00', 'view');
INSERT INTO events VALUES (11, 3, '2026-03-01 12:00:00', 'buy');
```

**Your query should return**

| user_id | session_no | session_start | first_buy | minutes_to_buy |
|---|---|---|---|---|
| 1 | 1 | 2026-03-01 09:00:00 | 2026-03-01 09:52:00 | 52 |
| 1 | 2 | 2026-03-01 10:23:00 | 2026-03-01 10:30:00 | 7 |
| 2 | 1 | 2026-03-01 23:50:00 | 2026-03-02 00:15:00 | 25 |
| 3 | 1 | 2026-03-01 12:00:00 | 2026-03-01 12:00:00 | 0 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    WITH e AS (
        SELECT user_id, event_id, ts, event,
               CASE WHEN LAG(ts) OVER w IS NULL
                      OR ts - LAG(ts) OVER w > INTERVAL '30 minutes' THEN 1 ELSE 0 END AS new_session
        FROM events
        WINDOW w AS (PARTITION BY user_id ORDER BY ts, event_id)
    ),
    s AS (
        SELECT user_id, ts, event,
               SUM(new_session) OVER (PARTITION BY user_id ORDER BY ts, event_id
                                      ROWS UNBOUNDED PRECEDING) AS session_no
        FROM e
    )
    SELECT user_id, session_no,
           MIN(ts) AS session_start,
           MIN(ts) FILTER (WHERE event = 'buy') AS first_buy,
           (EXTRACT(EPOCH FROM MIN(ts) FILTER (WHERE event = 'buy') - MIN(ts)) / 60)::int AS minutes_to_buy
    FROM s
    GROUP BY user_id, session_no
    HAVING COUNT(*) FILTER (WHERE event = 'buy') > 0
    ORDER BY user_id, session_no;
    ```

    **Why it works**

    1. `LAG(ts)` is the user's previous event. A first event, or a gap over 30 minutes, gets a 1 in `new_session`.
    2. A running `SUM` of those 1s numbers the sessions. `ROWS UNBOUNDED PRECEDING` gives each row its own count even if
       two rows were ever at the same time.
    3. The gap from 09:10 to 09:40 is exactly 30 minutes, so it is the same session; 09:52 to 10:23 is 31 and starts
       session 2. User 2's session runs past midnight; time differences on full timestamps do not care.
    4. `MIN(ts) FILTER (WHERE event = 'buy')` is the first buy only (10:30, not 10:35). `HAVING` drops sessions with no
       buy, like user 2's 08:00 visit.
    5. `EXTRACT(EPOCH FROM interval)` is seconds as a `numeric`; divided by 60 and cast to `int` it prints as `52`, not
       `52.000000`.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 3. Percent change month on month per region

**Topic:** percent change with NULLIF

Each row of `orders` is an order or a refund (negative `amount`). Every region has at least one row in every month
from its first month to its last, so there are no missing months.

For each region and month return `region`, `month` (first day, as a date), `revenue` (net sum) and `pct_change`:
the change from the region's previous month in percent, rounded to one decimal. It is `NULL` for a region's first
month, and `NULL` when the previous month's revenue was 0 (there is no percent of zero). Sort by `region`, then
`month`.

**Tables and example data**

```sql
CREATE TABLE orders (
    order_id   INTEGER PRIMARY KEY,
    region     TEXT NOT NULL,
    order_date DATE NOT NULL,
    amount     INTEGER NOT NULL
);
INSERT INTO orders VALUES (1, 'East', '2026-01-05', 300);
INSERT INTO orders VALUES (2, 'East', '2026-01-20', 100);
INSERT INTO orders VALUES (3, 'East', '2026-02-11', 500);
INSERT INTO orders VALUES (4, 'East', '2026-03-02', 300);
INSERT INTO orders VALUES (5, 'East', '2026-03-31', 0);
INSERT INTO orders VALUES (6, 'West', '2026-01-09', 200);
INSERT INTO orders VALUES (7, 'West', '2026-02-14', 150);
INSERT INTO orders VALUES (8, 'West', '2026-02-15', -150);
INSERT INTO orders VALUES (9, 'West', '2026-03-01', 90);
INSERT INTO orders VALUES (10, 'West', '2026-03-20', 30);
INSERT INTO orders VALUES (11, 'West', '2026-04-03', 40);
```

**Your query should return**

| region | month | revenue | pct_change |
|---|---|---|---|
| East | 2026-01-01 | 400 | NULL |
| East | 2026-02-01 | 500 | 25.0 |
| East | 2026-03-01 | 300 | -40.0 |
| West | 2026-01-01 | 200 | NULL |
| West | 2026-02-01 | 0 | -100.0 |
| West | 2026-03-01 | 120 | NULL |
| West | 2026-04-01 | 40 | -66.7 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    WITH m AS (
        SELECT region, date_trunc('month', order_date)::date AS month, SUM(amount) AS revenue
        FROM orders
        GROUP BY region, date_trunc('month', order_date)
    )
    SELECT region, month, revenue,
           ROUND(100.0 * (revenue - LAG(revenue) OVER w)
                       / NULLIF(LAG(revenue) OVER w, 0), 1) AS pct_change
    FROM m
    WINDOW w AS (PARTITION BY region ORDER BY month)
    ORDER BY region, month;
    ```

    **Why it works**

    1. Sum per month first, then compare months with `LAG` inside each region (`PARTITION BY region`).
    2. `NULLIF(prev, 0)` turns a zero divisor into `NULL`, and anything divided by `NULL` is `NULL`. Without it, West's
       March (after a February that netted to 0) stops the whole query with "division by zero".
    3. `100.0 *` makes the maths `numeric`. With two whole numbers PostgreSQL does integer division and -80 / 120 gives 0.
    4. West's April compares with March (120), not with February: -80 / 120 = -66.7 %. East's March has a zero-dollar
       order, which changes nothing.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 4. Median and 90th percentile delivery time

**Topic:** median with percentile_cont

`deliveries` has one row per parcel; `hours` is how long it took, or `NULL` if it has not arrived yet.

For each carrier return `carrier`, `delivered` (parcels with a time), `median_hours` and `p90_hours`, both as the
continuous percentile (between two values it takes the point in between), rounded to one decimal. Sort by
`carrier`.

**Tables and example data**

```sql
CREATE TABLE deliveries (
    delivery_id INTEGER PRIMARY KEY,
    carrier     TEXT NOT NULL,
    hours       INTEGER
);
INSERT INTO deliveries VALUES (1, 'Falcon', 20);
INSERT INTO deliveries VALUES (2, 'Falcon', 26);
INSERT INTO deliveries VALUES (3, 'Falcon', 22);
INSERT INTO deliveries VALUES (4, 'Falcon', 48);
INSERT INTO deliveries VALUES (5, 'Falcon', 24);
INSERT INTO deliveries VALUES (6, 'Heron', 30);
INSERT INTO deliveries VALUES (7, 'Heron', 12);
INSERT INTO deliveries VALUES (8, 'Heron', NULL);
INSERT INTO deliveries VALUES (9, 'Heron', 18);
INSERT INTO deliveries VALUES (10, 'Heron', 60);
INSERT INTO deliveries VALUES (11, 'Otter', 36);
```

**Your query should return**

| carrier | delivered | median_hours | p90_hours |
|---|---|---|---|
| Falcon | 5 | 24.0 | 39.2 |
| Heron | 4 | 24.0 | 51.0 |
| Otter | 1 | 36.0 | 36.0 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    SELECT carrier,
           COUNT(hours) AS delivered,
           ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY hours))::numeric, 1) AS median_hours,
           ROUND((percentile_cont(0.9) WITHIN GROUP (ORDER BY hours))::numeric, 1) AS p90_hours
    FROM deliveries
    GROUP BY carrier
    ORDER BY carrier;
    ```

    **Why it works**

    1. `percentile_cont(0.5) WITHIN GROUP (ORDER BY hours)` is the median: the middle value for an odd count (Falcon:
       24), the average of the two middle ones for an even count (Heron: 18 and 30 give 24).
    2. For 0.9 it finds position 0.9 x (n - 1) in the sorted list and goes that far between the two neighbours.
       Falcon: position 3.6, between 26 and 48, so 26 + 0.6 x 22 = 39.2. Heron: position 2.7, between 30 and 60, so 51.
    3. Like other aggregates it skips `NULL`, so Heron's parcel still on the way is not counted; `COUNT(hours)` skips it
       too, `COUNT(*)` would not.
    4. The result is `double precision`, which can print as 39.199999999999996; `::numeric` and `ROUND(..., 1)` give
       39.2. `percentile_disc` would pick a real row's value (26) instead of a point between.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 5. Units per month as columns, with a total row

**Topic:** pivot with FILTER

`sales` lists units sold per product per day. For the first quarter of 2026 only (1 January to 31 March), return
one row per product that sold in that quarter, with columns `product`, `jan`, `feb`, `mar` and `total` (0 where a
product sold nothing that month). Sort products by `total` from most to least, then by name, and end with one row
`TOTAL` that adds up each column.

**Tables and example data**

```sql
CREATE TABLE sales (
    sale_id   INTEGER PRIMARY KEY,
    product   TEXT NOT NULL,
    sale_date DATE NOT NULL,
    units     INTEGER NOT NULL
);
INSERT INTO sales VALUES (1, 'Lamp', '2026-01-04', 3);
INSERT INTO sales VALUES (2, 'Lamp', '2026-01-31', 2);
INSERT INTO sales VALUES (3, 'Lamp', '2026-02-01', 4);
INSERT INTO sales VALUES (4, 'Lamp', '2026-03-15', 1);
INSERT INTO sales VALUES (5, 'Desk', '2026-01-10', 1);
INSERT INTO sales VALUES (6, 'Desk', '2026-03-30', 2);
INSERT INTO sales VALUES (7, 'Chair', '2026-02-20', 6);
INSERT INTO sales VALUES (8, 'Chair', '2025-12-31', 9);
INSERT INTO sales VALUES (9, 'Shelf', '2026-04-01', 5);
```

**Your query should return**

| product | jan | feb | mar | total |
|---|---|---|---|---|
| Lamp | 5 | 4 | 1 | 10 |
| Chair | 0 | 6 | 0 | 6 |
| Desk | 1 | 0 | 2 | 3 |
| TOTAL | 6 | 10 | 3 | 19 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    WITH p AS (
        SELECT product,
               COALESCE(SUM(units) FILTER (WHERE sale_date < '2026-02-01'), 0) AS jan,
               COALESCE(SUM(units) FILTER (WHERE sale_date >= '2026-02-01' AND sale_date < '2026-03-01'), 0) AS feb,
               COALESCE(SUM(units) FILTER (WHERE sale_date >= '2026-03-01'), 0) AS mar
        FROM sales
        WHERE sale_date >= '2026-01-01' AND sale_date < '2026-04-01'
        GROUP BY product
    ),
    t AS (
        SELECT product, jan, feb, mar, jan + feb + mar AS total, 0 AS k FROM p
        UNION ALL
        SELECT 'TOTAL', SUM(jan), SUM(feb), SUM(mar), SUM(jan + feb + mar), 1 FROM p
    )
    SELECT product, jan, feb, mar, total
    FROM t
    ORDER BY k, total DESC, product;
    ```

    **Why it works**

    1. One `GROUP BY product` and one filtered `SUM` per month turns rows into columns; `COALESCE` turns a month with no
       rows (`NULL`) into 0.
    2. The `WHERE` keeps the quarter, so Chair's 31 December sale and Shelf's 1 April sale are out, and Shelf has no row.
       Comparing a date with `'2026-02-01'` works because PostgreSQL reads the text as a date.
    3. The `TOTAL` row is a second `SELECT` glued on with `UNION ALL`. The helper column `k` (0 for products, 1 for the
       total) keeps it last whatever the totals are; it is used in `ORDER BY` but not shown.
    4. In PostgreSQL `ROLLUP` could make the total row too, but the `UNION ALL` form is easy to read and runs anywhere.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 6. Referral bonus down the chain

**Topic:** recursive CTE for a referral chain

`users.referred_by` is the user who brought this user in (`NULL` if nobody did). There are no loops. A referrer
earns 10 dollars for each person they referred directly, 5 for each person those people referred, and nothing
deeper down.

For every user who referred at least one person, return `name`, `direct` (people referred directly), `downline`
(everyone below them, at any depth), `depth` (how many levels go down below them) and `bonus`. Sort by `bonus` from
most to least, then `name`.

**Tables and example data**

```sql
CREATE TABLE users (
    user_id     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    referred_by INTEGER
);
INSERT INTO users VALUES (1, 'Ana', NULL);
INSERT INTO users VALUES (2, 'Ben', 1);
INSERT INTO users VALUES (3, 'Cleo', 1);
INSERT INTO users VALUES (4, 'Dev', 2);
INSERT INTO users VALUES (5, 'Eli', 4);
INSERT INTO users VALUES (6, 'Fay', 5);
INSERT INTO users VALUES (7, 'Gus', NULL);
INSERT INTO users VALUES (8, 'Hana', 7);
INSERT INTO users VALUES (9, 'Ivo', 3);
```

**Your query should return**

| name | direct | downline | depth | bonus |
|---|---|---|---|---|
| Ana | 2 | 6 | 4 | 30 |
| Ben | 1 | 3 | 3 | 15 |
| Dev | 1 | 2 | 2 | 15 |
| Cleo | 1 | 1 | 1 | 10 |
| Eli | 1 | 1 | 1 | 10 |
| Gus | 1 | 1 | 1 | 10 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    WITH RECURSIVE down AS (
        SELECT referred_by AS top_id, user_id, 1 AS lvl
        FROM users
        WHERE referred_by IS NOT NULL
        UNION ALL
        SELECT d.top_id, u.user_id, d.lvl + 1
        FROM down d
        JOIN users u ON u.referred_by = d.user_id
    )
    SELECT t.name,
           COUNT(*) FILTER (WHERE d.lvl = 1) AS direct,
           COUNT(*) AS downline,
           MAX(d.lvl) AS depth,
           SUM(CASE d.lvl WHEN 1 THEN 10 WHEN 2 THEN 5 ELSE 0 END) AS bonus
    FROM down d
    JOIN users t ON t.user_id = d.top_id
    GROUP BY t.user_id, t.name
    ORDER BY bonus DESC, t.name;
    ```

    **Why it works**

    1. The first part of the CTE gives every referral link as level 1: (referrer, new user).
    2. The recursive part follows the chain down: if X is in Y's downline at level n, then the people X referred are in
       Y's downline at level n + 1. It stops when a step finds no new rows.
    3. Each row is (top, someone below, level), so one `GROUP BY` gives all four numbers. Ana: Ben and Cleo at 1, Dev
       and Ivo at 2, Eli at 3, Fay at 4, so bonus 10 + 10 + 5 + 5 = 30.
    4. With a loop in the data (A referred B, B referred A) this would never stop. PostgreSQL 14 and later can guard it
       with `CYCLE user_id SET is_cycle USING path`, which this data does not need.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 7. Missing training, three ways

**Topic:** anti-join three ways

Every employee must finish every course in `required`. `done` records completions; it can hold the same course
twice, courses that are not required, and rows whose `course` was lost (`NULL`), which count as nothing.

Return each employee and required course that is **not** done: `name`, `course`. Sort by `name`, then `course`.
Write it three ways: `NOT EXISTS`, `LEFT JOIN ... IS NULL` and `NOT IN`.

**Tables and example data**

```sql
CREATE TABLE employees (
    emp_id INTEGER PRIMARY KEY,
    name   TEXT NOT NULL
);
CREATE TABLE required (
    course TEXT PRIMARY KEY
);
CREATE TABLE done (
    emp_id INTEGER NOT NULL,
    course TEXT
);
INSERT INTO employees VALUES (1, 'Mia');
INSERT INTO employees VALUES (2, 'Noor');
INSERT INTO employees VALUES (3, 'Omar');
INSERT INTO required VALUES ('fire');
INSERT INTO required VALUES ('privacy');
INSERT INTO required VALUES ('safety');
INSERT INTO done VALUES (1, 'fire');
INSERT INTO done VALUES (1, 'safety');
INSERT INTO done VALUES (1, 'excel');
INSERT INTO done VALUES (2, 'privacy');
INSERT INTO done VALUES (2, NULL);
INSERT INTO done VALUES (3, 'fire');
INSERT INTO done VALUES (3, 'fire');
INSERT INTO done VALUES (3, 'privacy');
INSERT INTO done VALUES (3, 'safety');
```

**Your query should return**

| name | course |
|---|---|
| Mia | privacy |
| Noor | fire |
| Noor | safety |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    **Solution 1: NOT EXISTS**

    ```sql
    SELECT e.name, r.course
    FROM employees e
    CROSS JOIN required r
    WHERE NOT EXISTS (
        SELECT 1 FROM done d
        WHERE d.emp_id = e.emp_id AND d.course = r.course
    )
    ORDER BY e.name, r.course;
    ```

    **Solution 2: LEFT JOIN ... IS NULL**

    ```sql
    SELECT e.name, r.course
    FROM employees e
    CROSS JOIN required r
    LEFT JOIN done d ON d.emp_id = e.emp_id AND d.course = r.course
    WHERE d.emp_id IS NULL
    ORDER BY e.name, r.course;
    ```

    **Solution 3: NOT IN**

    ```sql
    SELECT e.name, r.course
    FROM employees e
    CROSS JOIN required r
    WHERE (e.emp_id, r.course) NOT IN (
        SELECT emp_id, course FROM done WHERE course IS NOT NULL
    )
    ORDER BY e.name, r.course;
    ```

    **The trap, for comparison (wrong answer):** `NOT IN` without the `IS NOT NULL` filter

    ```sql
    SELECT e.name, r.course
    FROM employees e
    CROSS JOIN required r
    WHERE (e.emp_id, r.course) NOT IN (
        SELECT emp_id, course FROM done
    )
    ORDER BY e.name, r.course;
    ```

    **Why it works**

    1. `CROSS JOIN` builds every (employee, required course) pair, 9 here. The anti-join keeps the pairs with no
       matching row in `done`.
    2. `NOT EXISTS` is the safe default: it only asks "is there a match", so duplicate rows (Omar's two `fire` rows) and
       `NULL`s do no harm.
    3. `LEFT JOIN` keeps a pair with `NULL`s on the `done` side when there is no match; `WHERE d.emp_id IS NULL` keeps only
       those. Test a column that can never be `NULL` in a real match (here `emp_id`, which is `NOT NULL`).
    4. `NOT IN` is the trap. Noor's row `(2, NULL)`: is `(2, 'fire')` equal to it? The answer is unknown, not no, so
       `NOT IN` is unknown and Noor's missing pairs vanish. Other employees are not hit, since `1 = 2` is a clear no.
       Filtering `course IS NOT NULL` inside fixes it. Run the trap: it returns only Mia's row.
    5. PostgreSQL usually plans `NOT EXISTS` and the `LEFT JOIN` form the same way (an anti-join); `NOT IN` cannot use that
       plan because of the `NULL` rule.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 8. Nurses booked on overlapping shifts

**Topic:** self-join for overlapping periods

`shifts` lists each nurse's shifts; a shift may run past midnight. A nurse is double-booked when two of their
shifts overlap. A shift that starts the moment another ends (15:00 to 15:00) is fine.

Return each double-booked pair once: `nurse`, `shift_a`, `shift_b` (`shift_a < shift_b`) and `overlap_minutes`.
Sort by `nurse`, `shift_a`, `shift_b`.

**Tables and example data**

```sql
CREATE TABLE shifts (
    shift_id INTEGER PRIMARY KEY,
    nurse    TEXT NOT NULL,
    ward     TEXT NOT NULL,
    start_ts TIMESTAMP NOT NULL,
    end_ts   TIMESTAMP NOT NULL
);
INSERT INTO shifts VALUES (1, 'Kim', 'A', '2026-03-01 07:00:00', '2026-03-01 15:00:00');
INSERT INTO shifts VALUES (2, 'Kim', 'B', '2026-03-01 15:00:00', '2026-03-01 23:00:00');
INSERT INTO shifts VALUES (3, 'Kim', 'C', '2026-03-01 22:00:00', '2026-03-02 06:00:00');
INSERT INTO shifts VALUES (4, 'Lee', 'A', '2026-03-01 07:00:00', '2026-03-01 19:00:00');
INSERT INTO shifts VALUES (5, 'Lee', 'B', '2026-03-01 09:30:00', '2026-03-01 11:45:00');
INSERT INTO shifts VALUES (6, 'Lee', 'C', '2026-03-01 18:00:00', '2026-03-02 02:00:00');
INSERT INTO shifts VALUES (7, 'Max', 'A', '2026-03-01 07:00:00', '2026-03-01 15:00:00');
INSERT INTO shifts VALUES (8, 'Kim', 'A', '2026-03-02 07:00:00', '2026-03-02 15:00:00');
```

**Your query should return**

| nurse | shift_a | shift_b | overlap_minutes |
|---|---|---|---|
| Kim | 2 | 3 | 60 |
| Lee | 4 | 5 | 135 |
| Lee | 4 | 6 | 60 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    SELECT a.nurse, a.shift_id AS shift_a, b.shift_id AS shift_b,
           (EXTRACT(EPOCH FROM LEAST(a.end_ts, b.end_ts) - GREATEST(a.start_ts, b.start_ts)) / 60)::int
               AS overlap_minutes
    FROM shifts a
    JOIN shifts b ON b.nurse = a.nurse
                 AND a.shift_id < b.shift_id
                 AND a.start_ts < b.end_ts
                 AND b.start_ts < a.end_ts
    ORDER BY a.nurse, shift_a, shift_b;
    ```

    **Why it works**

    1. Two periods overlap exactly when each starts before the other ends: `a.start < b.end AND b.start < a.end`. This
       one test covers partial overlaps, one shift inside another (Lee 4 and 5) and overnight shifts.
    2. Strict `<` lets Kim's 07:00-15:00 and 15:00-23:00 touch without counting.
    3. `a.shift_id < b.shift_id` lists each pair once and never pairs a shift with itself.
    4. The overlap runs from the later start to the earlier end: `LEAST(ends) - GREATEST(starts)`, an interval, turned
       into whole minutes with `EXTRACT(EPOCH ...) / 60`.
    5. PostgreSQL also has range types: `tsrange(a.start_ts, a.end_ts) && tsrange(b.start_ts, b.end_ts)` is the same
       test, since a `tsrange` leaves out its end by default.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.
