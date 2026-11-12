# SQL practice: set 3

Eight more tasks in the style of the [SQL practice set](sql-practice.md): runner-up salary, seats nobody took, a median from counts, histogram buckets, entry and exit pages, a three-day streak, budget against actual, and a parts list. Every solution was run on PostgreSQL 16 and SQLite 3.54 with the example and gave exactly the expected result. They have not had random or large-table tests, so write your own edge cases before you open a solution.

### 1. Runner-up salary in each department

**Topic:** second highest per group

Each row is one employee. For every department return `dept` and `runner_up`: the second-highest **distinct** salary in that department. A department where everyone earns the same, or with one person, still appears, with `NULL`. Sort by `dept`.

**Tables and example data**

```sql
CREATE TABLE staff (
    emp_id INTEGER PRIMARY KEY,
    dept   TEXT NOT NULL,
    salary INTEGER NOT NULL
);
INSERT INTO staff VALUES (1, 'ops', 5000), (2, 'ops', 7000), (3, 'ops', 7000), (4, 'ops', 6000);
INSERT INTO staff VALUES (5, 'law', 9000), (6, 'law', 9000);
INSERT INTO staff VALUES (7, 'art', 4000);
INSERT INTO staff VALUES (8, 'dev', 8000), (9, 'dev', 6500), (10, 'dev', 6500), (11, 'dev', 3000);
```

**Your query should return**

| dept | runner_up |
|---|---|
| art |  |
| dev | 6500 |
| law |  |
| ops | 6000 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**

    ```sql
    WITH r AS (
        SELECT dept, salary,
               DENSE_RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS rk
        FROM staff
    )
    SELECT dept, MAX(CASE WHEN rk = 2 THEN salary END) AS runner_up
    FROM r
    GROUP BY dept
    ORDER BY dept;
    ```

    **Why it works**

    1. `DENSE_RANK` gives equal salaries the same rank and does not skip, so rank 2 is the second distinct salary (ops: 7000, 7000 are both 1, 6000 is 2).
    2. Grouping by `dept` keeps every department; `MAX(CASE ...)` is `NULL` when no row has rank 2 (law, art).
    3. Filtering `WHERE rk = 2` before grouping would drop law and art, and `ROW_NUMBER` would wrongly give ops 7000.

    **Tested on PostgreSQL 16 and SQLite 3.54** with the example above: exactly the expected rows, columns and order on both.


### 2. Planned seats nobody took

**Topic:** rows in A not in B on two columns

`planned` lists the (student, course) pairs an adviser planned; `enrolled` lists the pairs that really enrolled. The same student and the same course can each appear in other pairs. Return the planned pairs with no matching enrolment on **both** columns: `student`, `course`. List each pair once even if it was planned twice. Sort by `student`, then `course`.

**Tables and example data**

```sql
CREATE TABLE planned (student TEXT NOT NULL, course TEXT NOT NULL);
CREATE TABLE enrolled (student TEXT NOT NULL, course TEXT NOT NULL, term TEXT NOT NULL);
INSERT INTO planned VALUES ('ana', 'bio'), ('ana', 'chem'), ('ben', 'bio'), ('ben', 'math');
INSERT INTO planned VALUES ('cy', 'art'), ('cy', 'art'), ('dee', 'chem');
INSERT INTO enrolled VALUES ('ana', 'bio', 'fall'), ('ben', 'chem', 'fall'), ('cy', 'bio', 'fall');
INSERT INTO enrolled VALUES ('ben', 'math', 'fall'), ('ben', 'math', 'winter'), ('dee', 'chem', 'winter');
```

**Your query should return**

| student | course |
|---|---|
| ana | chem |
| ben | bio |
| cy | art |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**

    ```sql
    SELECT DISTINCT p.student, p.course
    FROM planned p
    WHERE NOT EXISTS (
        SELECT 1 FROM enrolled e
        WHERE e.student = p.student AND e.course = p.course
    )
    ORDER BY p.student, p.course;
    ```

    **Why it works**

    1. `NOT EXISTS` with both columns in the inner `WHERE` checks the pair, not each column on its own.
    2. Two separate tests (`student NOT IN ... AND course NOT IN ...`) would drop ana/chem and ben/bio, because ana and bio each appear elsewhere.
    3. An inner join would repeat ben/math once per term; `NOT EXISTS` stops at the first match, and `DISTINCT` folds the double cy/art plan.

    **Tested on PostgreSQL 16 and SQLite 3.54** with the example above: exactly the expected rows, columns and order on both.


### 3. Median from a count table

**Topic:** median without PERCENTILE

A survey stored its answers already counted: each row says that `cnt` people gave the whole-number answer `score` (`cnt` is at least 1, each score once). Return one row, `median_score`: the median of all the individual answers, as if every answer had its own row. For an even number of answers it is the average of the two middle ones. Do not use `PERCENTILE_CONT` or `MEDIAN`.

**Tables and example data**

```sql
CREATE TABLE answers (
    score INTEGER PRIMARY KEY,
    cnt   INTEGER NOT NULL
);
INSERT INTO answers VALUES (1, 3), (2, 1), (3, 2), (4, 4), (5, 2);
```

**Your query should return**

| median_score |
|---|
| 3.5 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**

    ```sql
    WITH c AS (
        SELECT score,
               SUM(cnt) OVER (ORDER BY score) - cnt + 1 AS first_pos,
               SUM(cnt) OVER (ORDER BY score) AS last_pos,
               SUM(cnt) OVER () AS n
        FROM answers
    )
    SELECT AVG(score * 1.0) AS median_score
    FROM c
    WHERE (n + 1) / 2 BETWEEN first_pos AND last_pos
       OR (n + 2) / 2 BETWEEN first_pos AND last_pos;
    ```

    **Why it works**

    1. The running sum of `cnt` tells which positions each score covers when all answers are sorted (score 3 covers positions 5 and 6 of 12).
    2. With integer division, `(n+1)/2` and `(n+2)/2` are the two middle positions (6 and 7 here); for odd `n` they are the same one.
    3. The rows that cover those positions are averaged, 3 and 4 give 3.5; if both fall in one score, `AVG` of one row is that score. Expanding the rows first also works but makes `n` rows.

    **Tested on PostgreSQL 16 and SQLite 3.54** with the example above: exactly the expected rows, columns and order on both.


### 4. Response times in 100 ms buckets

**Topic:** histogram buckets

Each row is one request with its time in milliseconds (`ms` is 0 or more). Put the times into buckets 100 ms wide: 0-99, 100-199, and so on. Return `bucket_start`, `bucket_end` and `requests` for **every** bucket from 0 up to the bucket of the slowest request, with 0 for empty ones. Sort by `bucket_start`.

**Tables and example data**

```sql
CREATE TABLE requests (
    req_id INTEGER PRIMARY KEY,
    ms     INTEGER NOT NULL
);
INSERT INTO requests VALUES (1, 12), (2, 99), (3, 100), (4, 150), (5, 180);
INSERT INTO requests VALUES (6, 199), (7, 420), (8, 455), (9, 61);
```

**Your query should return**

| bucket_start | bucket_end | requests |
|---|---|---|
| 0 | 99 | 3 |
| 100 | 199 | 4 |
| 200 | 299 | 0 |
| 300 | 399 | 0 |
| 400 | 499 | 2 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**

    ```sql
    WITH RECURSIVE b(bucket_start) AS (
        SELECT 0
        UNION ALL
        SELECT bucket_start + 100 FROM b
        WHERE bucket_start + 100 <= (SELECT MAX(ms) FROM requests)
    )
    SELECT b.bucket_start, b.bucket_start + 99 AS bucket_end, COUNT(r.req_id) AS requests
    FROM b
    LEFT JOIN requests r ON r.ms - r.ms % 100 = b.bucket_start
    GROUP BY b.bucket_start
    ORDER BY b.bucket_start;
    ```

    **Why it works**

    1. `ms - ms % 100` rounds a time down to its bucket (199 goes to 100, 100 stays 100).
    2. The recursive CTE makes every bucket start from 0 to the slowest request, so 200 and 300 exist even with no rows.
    3. `LEFT JOIN` keeps empty buckets and `COUNT(r.req_id)` counts only real matches; `COUNT(*)` would show 1 for them. Task 10 on the page has fixed bands; here they come from the data.

    **Tested on PostgreSQL 16 and SQLite 3.54** with the example above: exactly the expected rows, columns and order on both.


### 5. Entry and exit page of each visit

**Topic:** first and last event per session

Each row is one page view inside a visit (`visit_id`); `t` is the second it happened, and no visit has two views at the same second. For every visit return `visit_id`, `entry_page` (first page), `exit_page` (last page), `views` and `seconds` (last `t` minus first `t`). Sort by `visit_id`.

**Tables and example data**

```sql
CREATE TABLE views (
    visit_id INTEGER NOT NULL,
    t        INTEGER NOT NULL,
    page     TEXT NOT NULL
);
INSERT INTO views VALUES (1, 100, 'home'), (1, 130, 'search'), (1, 190, 'item'), (1, 250, 'cart');
INSERT INTO views VALUES (2, 40, 'item'), (2, 300, 'home');
INSERT INTO views VALUES (3, 500, 'help');
INSERT INTO views VALUES (4, 70, 'home'), (4, 10, 'blog'), (4, 90, 'blog');
```

**Your query should return**

| visit_id | entry_page | exit_page | views | seconds |
|---|---|---|---|---|
| 1 | home | cart | 4 | 150 |
| 2 | item | home | 2 | 260 |
| 3 | help | help | 1 | 0 |
| 4 | blog | blog | 3 | 80 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**

    ```sql
    WITH w AS (
        SELECT visit_id, t, page,
               FIRST_VALUE(page) OVER (PARTITION BY visit_id ORDER BY t) AS entry_page,
               FIRST_VALUE(page) OVER (PARTITION BY visit_id ORDER BY t DESC) AS exit_page
        FROM views
    )
    SELECT visit_id, MIN(entry_page) AS entry_page, MIN(exit_page) AS exit_page,
           COUNT(*) AS views, MAX(t) - MIN(t) AS seconds
    FROM w
    GROUP BY visit_id
    ORDER BY visit_id;
    ```

    **Why it works**

    1. `FIRST_VALUE` over `t` ascending gives the entry page on every row of the visit; over `t DESC` it gives the exit page.
    2. `LAST_VALUE(page) ... ORDER BY t` looks right but is wrong: its default frame ends at the current row, so it returns each row's own page.
    3. Every row of a visit holds the same two values, so `MIN` just picks them while grouping; visit 4 shows rows need not be stored in time order.

    **Tested on PostgreSQL 16 and SQLite 3.54** with the example above: exactly the expected rows, columns and order on both.


### 6. First time a user came three days running

**Topic:** users active three days in a row

Each row is one login; `day` is a day number (1, 2, 3, ...), and a user can log in many times a day. For every user who logged in on three or more consecutive days, return `user_id` and `third_day`: the earliest day on which they completed three days in a row. Users without such a run are left out. Sort by `user_id`.

**Tables and example data**

```sql
CREATE TABLE logins (
    user_id INTEGER NOT NULL,
    day     INTEGER NOT NULL
);
INSERT INTO logins VALUES (1, 1), (1, 2), (1, 2), (1, 4), (1, 5), (1, 6), (1, 7);
INSERT INTO logins VALUES (2, 3), (2, 3), (2, 3), (2, 4);
INSERT INTO logins VALUES (3, 10), (3, 11), (3, 12), (3, 20), (3, 21), (3, 22);
INSERT INTO logins VALUES (4, 1), (4, 3), (4, 5);
```

**Your query should return**

| user_id | third_day |
|---|---|
| 1 | 6 |
| 3 | 12 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**

    ```sql
    WITH d AS (
        SELECT DISTINCT user_id, day FROM logins
    ),
    w AS (
        SELECT user_id, day,
               LAG(day, 2) OVER (PARTITION BY user_id ORDER BY day) AS day_2_back
        FROM d
    )
    SELECT user_id, MIN(day) AS third_day
    FROM w
    WHERE day_2_back = day - 2
    GROUP BY user_id
    ORDER BY user_id;
    ```

    **Why it works**

    1. `DISTINCT` first: user 2 logs in three times on day 3, which must not count as three days.
    2. After that each day appears once per user, so if the day two rows back is exactly `day - 2`, the middle one is `day - 1` and the three are in a row.
    3. `MIN(day)` picks the first such day; user 1 reaches it on day 6 (4, 5, 6), not on day 2. Task 50 finds the longest run; this asks when a run of three first ends.

    **Tested on PostgreSQL 16 and SQLite 3.54** with the example above: exactly the expected rows, columns and order on both.


### 7. Budget against actual spending by month

**Topic:** budget versus actual with missing months

`budget` holds the planned amount per team and month; `spend` holds each payment. A month can have a budget and no spending, spending and no budget, or neither. `months` lists the months of the report. For every team in `budget` and every month in `months` return `team`, `month`, `budget`, `actual` and `diff` (actual minus budget), with 0 where a side is missing. Sort by `team`, then `month`.

**Tables and example data**

```sql
CREATE TABLE months (month TEXT PRIMARY KEY);
CREATE TABLE budget (team TEXT NOT NULL, month TEXT NOT NULL, amount INTEGER NOT NULL);
CREATE TABLE spend (pay_id INTEGER PRIMARY KEY, team TEXT NOT NULL, month TEXT NOT NULL, amount INTEGER NOT NULL);
INSERT INTO months VALUES ('2026-01'), ('2026-02'), ('2026-03');
INSERT INTO budget VALUES ('lab', '2026-01', 500), ('lab', '2026-02', 500), ('web', '2026-01', 300), ('web', '2026-03', 300);
INSERT INTO spend VALUES (1, 'lab', '2026-01', 200), (2, 'lab', '2026-01', 350), (3, 'lab', '2026-03', 90);
INSERT INTO spend VALUES (4, 'web', '2026-01', 280), (5, 'web', '2026-02', 40), (6, 'web', '2026-02', 60);
```

**Your query should return**

| team | month | budget | actual | diff |
|---|---|---|---|---|
| lab | 2026-01 | 500 | 550 | 50 |
| lab | 2026-02 | 500 | 0 | -500 |
| lab | 2026-03 | 0 | 90 | 90 |
| web | 2026-01 | 300 | 280 | -20 |
| web | 2026-02 | 0 | 100 | 100 |
| web | 2026-03 | 300 | 0 | -300 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**

    ```sql
    WITH grid AS (
        SELECT t.team, m.month
        FROM (SELECT DISTINCT team FROM budget) t
        CROSS JOIN months m
    ),
    b AS (SELECT team, month, SUM(amount) AS amt FROM budget GROUP BY team, month),
    s AS (SELECT team, month, SUM(amount) AS amt FROM spend GROUP BY team, month)
    SELECT g.team, g.month,
           COALESCE(b.amt, 0) AS budget,
           COALESCE(s.amt, 0) AS actual,
           COALESCE(s.amt, 0) - COALESCE(b.amt, 0) AS diff
    FROM grid g
    LEFT JOIN b ON b.team = g.team AND b.month = g.month
    LEFT JOIN s ON s.team = g.team AND s.month = g.month
    ORDER BY g.team, g.month;
    ```

    **Why it works**

    1. The grid (every team times every month) gives each row a home, so a month missing from both tables still shows.
    2. Each side is summed on its own before the joins; joining raw payments to budget rows first would count lab's January budget twice.
    3. `COALESCE(..., 0)` turns a missing side into 0, so `diff` is never `NULL`. A plain `FULL JOIN` of budget and spend would still miss a month with neither.

    **Tested on PostgreSQL 16 and SQLite 3.54** with the example above: exactly the expected rows, columns and order on both.


### 8. Parts list for one bike

**Topic:** recursive bill of materials

`bom` says that one `parent` item is built from `qty` of the `child` item. Items that are never a parent are raw parts. A part can be used in more than one place. Return the raw parts needed to build **one** `bike`: `part` and `total_qty` (summed over every place it is used). Sort by `part`.

**Tables and example data**

```sql
CREATE TABLE bom (
    parent TEXT NOT NULL,
    child  TEXT NOT NULL,
    qty    INTEGER NOT NULL
);
INSERT INTO bom VALUES ('bike', 'frame', 1), ('bike', 'wheel', 2), ('bike', 'seat', 1);
INSERT INTO bom VALUES ('wheel', 'rim', 1), ('wheel', 'spoke', 32), ('wheel', 'hub', 1);
INSERT INTO bom VALUES ('hub', 'bolt', 2), ('hub', 'bearing', 2);
INSERT INTO bom VALUES ('frame', 'tube', 3), ('frame', 'bolt', 4);
INSERT INTO bom VALUES ('cart', 'wheel', 4);
```

**Your query should return**

| part | total_qty |
|---|---|
| bearing | 4 |
| bolt | 8 |
| rim | 2 |
| seat | 1 |
| spoke | 64 |
| tube | 3 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**

    ```sql
    WITH RECURSIVE need(item, qty) AS (
        SELECT child, qty FROM bom WHERE parent = 'bike'
        UNION ALL
        SELECT b.child, n.qty * b.qty
        FROM need n
        JOIN bom b ON b.parent = n.item
    )
    SELECT item AS part, SUM(qty) AS total_qty
    FROM need
    WHERE item NOT IN (SELECT parent FROM bom)
    GROUP BY item
    ORDER BY item;
    ```

    **Why it works**

    1. The start row is each direct child of `bike`; each step goes one level down and multiplies by the quantity so far (2 wheels times 32 spokes).
    2. `UNION ALL` keeps both paths to `bolt` (4 in the frame, 2 x 2 in the hubs); `UNION` would merge two equal rows and undercount.
    3. Only leaves are kept and summed; `cart` is never reached because the walk starts at `bike`. Task 37 counts levels; here amounts multiply along the path.

    **Tested on PostgreSQL 16 and SQLite 3.54** with the example above: exactly the expected rows, columns and order on both.
