# 31. Practice set B

*Twelve harder tasks, each on its own small table, the way a real test hands you a schema you have never seen.
Each task gives the tables (the SQL to create and fill them, ready to paste into a database), the exact result
your query should return on that data, and a hidden answer with the usual wrong answer run beside it. Every answer
ran on PostgreSQL 16 and SQLite 3.53, the two SQL dialects Codility offers on its practice tasks.*

!!! abstract "How to use this set"
    - **Paste the tables into a real database** and write your query there: SQLite in a terminal, the online
      [SQLite fiddle](https://sqlite.org/fiddle/), or PostgreSQL. Aim for the time given; a real test allows
      roughly 20 to 40 minutes per SQL task.
    - **Match the result exactly**: the same columns, in the same order, sorted as asked. Column names are shown for
      reading; a Codility checker compares the column order, not the names.
    - **Think about what the example leaves out.** Hidden tests add NULLs, ties, empty groups and rows that do not
      match. Several answers below add such a row and run the query again to show the difference.
    - These are different questions from the 28 in the [Codility test prep SQL practice
      set](../../interview/codility/sql-practice.md); do both. If a task stumps you, [Which technique does this
      wording ask for?](which-technique.md) maps its wording to a chapter.

    **You need:** chapters 1 to 16, from [1. tables and keys](01-Tables-Rows-and-Keys.md) to [16. dates](16-Dates-and-Time-Series.md). [Practice set A](30-Practice-Set-A.md) is the easier warm-up.

## Questions { #questions }

### B.1 Airline punctuality { #b1 }

**Level:** medium · **Aim for:** 15 minutes

Each row of `flights` is one flight. `delay_min` is the arrival delay in minutes (negative means early); it is NULL
when the flight was cancelled. For each airline, return `airline`, `flights` (all its flights), `cancelled`,
`avg_delay` (the average delay of the flights that flew, rounded to 1 decimal place) and `on_time_pct` (the
percentage of flights that flew that arrived at most 15 minutes late, rounded to 1 decimal place). An airline with
no flown flights shows NULL in the last two columns. Sort by `airline`.

<!-- sql setup -->
```sql
CREATE TABLE flights (
  flight_id   INTEGER PRIMARY KEY,
  airline     VARCHAR(20) NOT NULL,
  flight_date DATE NOT NULL,
  delay_min   INTEGER            -- NULL = cancelled
);
INSERT INTO flights VALUES
  (1, 'Aurora', '2026-05-01',    0),
  (2, 'Aurora', '2026-05-01',   25),
  (3, 'Aurora', '2026-05-02', NULL),
  (4, 'Aurora', '2026-05-03',   -5),
  (5, 'Boreal', '2026-05-01',   40),
  (6, 'Boreal', '2026-05-02',   15),
  (7, 'Boreal', '2026-05-03',   16),
  (8, 'Cirrus', '2026-05-01', NULL),
  (9, 'Cirrus', '2026-05-02', NULL),
  (10, 'Aurora', '2026-05-04',  10);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| airline | flights | cancelled | avg_delay | on_time_pct |
| --- | --- | --- | --- | --- |
| Aurora | 5 | 1 | 7.5 | 75.0 |
| Boreal | 3 | 0 | 23.7 | 33.3 |
| Cirrus | 2 | 2 | *NULL* | *NULL* |
<!-- /expected -->

??? success "Answer"
    <!-- sql expect -->
    ```sql
    SELECT airline,
           COUNT(*)                                             AS flights,
           SUM(CASE WHEN delay_min IS NULL THEN 1 ELSE 0 END)   AS cancelled,
           ROUND(AVG(delay_min), 1)                             AS avg_delay,
           ROUND(100.0 * SUM(CASE WHEN delay_min <= 15 THEN 1 ELSE 0 END)
                 / NULLIF(COUNT(delay_min), 0), 1)              AS on_time_pct
    FROM flights
    GROUP BY airline
    ORDER BY airline;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | airline | flights | cancelled | avg_delay | on_time_pct |
    | --- | --- | --- | --- | --- |
    | Aurora | 5 | 1 | 7.5 | 75.0 |
    | Boreal | 3 | 0 | 23.7 | 33.3 |
    | Cirrus | 2 | 2 | *NULL* | *NULL* |
    <!-- /result -->

    `COUNT(delay_min)` counts the flights that flew, because it skips NULLs; `AVG` skips them too. The
    `NULLIF(..., 0)` turns Cirrus's zero flown flights into NULL, so the division gives NULL instead of an error on
    PostgreSQL. An early flight (-5) has `delay_min <= 15` true, so it counts as on time, as it should.

    The usual wrong answer divides by `COUNT(*)`, counting cancelled flights as late:

    <!-- sql -->
    ```sql
    SELECT airline,
           ROUND(100.0 * SUM(CASE WHEN delay_min <= 15 THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_pct
    FROM flights
    GROUP BY airline
    ORDER BY airline;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | airline | on_time_pct |
    | --- | --- |
    | Aurora | 60.0 |
    | Boreal | 33.3 |
    | Cirrus | 0.0 |
    <!-- /result -->

    Aurora drops from 75.0 to 60.0, and Cirrus, which never flew, shows 0.0 instead of NULL. The other slip is to
    divide by `COUNT(delay_min)` without `NULLIF`:

    <!-- sql pgerror -->
    ```sql
    SELECT airline,
           ROUND(100.0 * SUM(CASE WHEN delay_min <= 15 THEN 1 ELSE 0 END) / COUNT(delay_min), 1) AS on_time_pct
    FROM flights
    GROUP BY airline
    ORDER BY airline;
    ```

    <!-- result -->
    <p class="sql-tested sql-error">PostgreSQL 16: error: <code>division by zero</code></p>
    <p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 3 rows.</p>
    <!-- /result -->

    PostgreSQL stops at Cirrus with "division by zero"; SQLite quietly gives NULL. A query that passes on SQLite can
    fail on PostgreSQL, so guard every divisor that can be 0.

### B.2 Overdue library loans { #b2 }

**Level:** medium · **Aim for:** 15 minutes

A loan is open while `returned_on` is NULL. As of 31 March 2026, list the open loans that have been out for **more
than 21 days**: `book_id`, `member_id`, `loaned_on`, `days_out`. Sort by `days_out` from most to fewest, then by
`book_id`.

<!-- sql setup -->
```sql
CREATE TABLE loans (
  loan_id     INTEGER PRIMARY KEY,
  book_id     INTEGER NOT NULL,
  member_id   INTEGER NOT NULL,
  loaned_on   DATE NOT NULL,
  returned_on DATE
);
INSERT INTO loans VALUES
  (1, 10, 1, '2026-02-01', '2026-02-20'),
  (2, 11, 1, '2026-03-01', NULL),
  (3, 12, 2, '2026-03-10', NULL),
  (4, 13, 3, '2026-01-15', NULL),
  (5, 10, 2, '2026-03-02', NULL),
  (6, 14, 3, '2026-03-20', '2026-03-25'),
  (7, 15, 4, '2026-02-28', '2026-03-31');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| book_id | member_id | loaned_on | days_out |
| --- | --- | --- | --- |
| 13 | 3 | 2026-01-15 | 75 |
| 11 | 1 | 2026-03-01 | 30 |
| 10 | 2 | 2026-03-02 | 29 |
<!-- /expected -->

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg expect -->
        ```sql
        SELECT book_id, member_id, loaned_on,
               CAST('2026-03-31' AS DATE) - loaned_on AS days_out
        FROM loans
        WHERE returned_on IS NULL
          AND CAST('2026-03-31' AS DATE) - loaned_on > 21
        ORDER BY days_out DESC, book_id;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

        | book_id | member_id | loaned_on | days_out |
        | --- | --- | --- | --- |
        | 13 | 3 | 2026-01-15 | 75 |
        | 11 | 1 | 2026-03-01 | 30 |
        | 10 | 2 | 2026-03-02 | 29 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        SELECT book_id, member_id, loaned_on,
               CAST(julianday('2026-03-31') - julianday(loaned_on) AS INTEGER) AS days_out
        FROM loans
        WHERE returned_on IS NULL
          AND julianday('2026-03-31') - julianday(loaned_on) > 21
        ORDER BY days_out DESC, book_id;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 3 rows.</p>

        | book_id | member_id | loaned_on | days_out |
        | --- | --- | --- | --- |
        | 13 | 3 | 2026-01-15 | 75 |
        | 11 | 1 | 2026-03-01 | 30 |
        | 10 | 2 | 2026-03-02 | 29 |
        <!-- /result -->

    Book 12 has been out exactly 21 days, which is not "more than 21", so it is left out; that boundary is what a
    hidden test checks. Book 15 came back on 31 March, so it is not open. On PostgreSQL, one `DATE` minus another is a
    whole number of days; the `CAST(... AS DATE)` makes the literal a date first (`DATE '2026-03-31'` also works).
    In a real system the date would be `CURRENT_DATE`.

### B.3 Price changes { #b3 }

**Level:** medium · **Aim for:** 15 minutes

`price_history` gets a row whenever a product's price is reviewed, even if the price stays the same. Return only the
reviews that **changed** the price: `product`, `changed_on`, `old_price`, `new_price`, `change_pct` (the change as a
percentage of the old price, rounded to 1 decimal place). A product's first row is not a change. Sort by `product`,
then `changed_on`.

<!-- sql setup -->
```sql
CREATE TABLE price_history (
  product    VARCHAR(20) NOT NULL,
  changed_on DATE NOT NULL,
  price      NUMERIC(8,2) NOT NULL,
  PRIMARY KEY (product, changed_on)
);
INSERT INTO price_history VALUES
  ('kettle', '2026-01-01', 30.00),
  ('kettle', '2026-02-01', 32.00),
  ('kettle', '2026-03-01', 32.00),
  ('kettle', '2026-04-01', 28.80),
  ('lamp',   '2026-01-15', 20.00),
  ('lamp',   '2026-03-15', 25.00),
  ('mug',    '2026-02-01',  8.00);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| product | changed_on | old_price | new_price | change_pct |
| --- | --- | --- | --- | --- |
| kettle | 2026-02-01 | 30.00 | 32.00 | 6.7 |
| kettle | 2026-04-01 | 32.00 | 28.80 | -10.0 |
| lamp | 2026-03-15 | 20.00 | 25.00 | 25.0 |
<!-- /expected -->

??? success "Answer"
    <!-- sql expect -->
    ```sql
    WITH h AS (
      SELECT product, changed_on,
             LAG(price) OVER (PARTITION BY product ORDER BY changed_on) AS old_price,
             price AS new_price
      FROM price_history
    )
    SELECT product, changed_on, old_price, new_price,
           ROUND(100.0 * (new_price - old_price) / old_price, 1) AS change_pct
    FROM h
    WHERE old_price IS NOT NULL
      AND new_price <> old_price
    ORDER BY product, changed_on;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | product | changed_on | old_price | new_price | change_pct |
    | --- | --- | --- | --- | --- |
    | kettle | 2026-02-01 | 30.00 | 32.00 | 6.7 |
    | kettle | 2026-04-01 | 32.00 | 28.80 | -10.0 |
    | lamp | 2026-03-15 | 20.00 | 25.00 | 25.0 |
    <!-- /result -->

    `LAG` must see **every** review, including the one that kept the kettle at 32.00; the filter comes after, in the
    outer query (a window cannot be filtered in its own `WHERE`). Any filter placed inside, before `LAG` runs (only
    the rows from February on, say), can make `LAG` compare with the wrong row: the kettle's 1 February change would
    then have no previous price and vanish. The
    mug's only row has no previous price, so `old_price IS NOT NULL` removes it. (SQLite shows the prices as `32` and
    `28.8`: it stores `NUMERIC` as plain numbers. The values are the same.)

### B.4 Above average in every subject { #b4 }

**Level:** medium-hard · **Aim for:** 20 minutes

Find the students whose score is **above the subject's average in every subject they took**. Return `student` and
`subjects` (how many subjects they took), sorted by `student`.

<!-- sql setup -->
```sql
CREATE TABLE exam_scores (
  student VARCHAR(10) NOT NULL,
  subject VARCHAR(10) NOT NULL,
  score   INTEGER NOT NULL,
  PRIMARY KEY (student, subject)
);
INSERT INTO exam_scores VALUES
  ('Ava',  'math',    90), ('Ava',  'physics', 70), ('Ava',  'art', 88),
  ('Ben',  'math',    60), ('Ben',  'physics', 85),
  ('Cleo', 'math',    80), ('Cleo', 'physics', 90), ('Cleo', 'art', 95),
  ('Dev',  'math',    75), ('Dev',  'art',     70),
  ('Eli',  'physics', 82);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| student | subjects |
| --- | --- |
| Cleo | 3 |
| Eli | 1 |
<!-- /expected -->

??? success "Answer"
    <!-- sql expect -->
    ```sql
    WITH s AS (
      SELECT student, subject, score,
             AVG(score) OVER (PARTITION BY subject) AS subject_avg
      FROM exam_scores
    )
    SELECT student, COUNT(*) AS subjects
    FROM s
    GROUP BY student
    HAVING MIN(CASE WHEN score > subject_avg THEN 1 ELSE 0 END) = 1
    ORDER BY student;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | student | subjects |
    | --- | --- |
    | Cleo | 3 |
    | Eli | 1 |
    <!-- /result -->

    The averages are math 76.25, physics 81.75, art 84.33. Each row gets 1 if it beats its subject's average, and
    "every" becomes "the smallest flag is 1". The usual wrong answer filters first and then groups, which answers
    "above average in **at least one** subject":

    <!-- sql -->
    ```sql
    WITH s AS (
      SELECT student, subject, score,
             AVG(score) OVER (PARTITION BY subject) AS subject_avg
      FROM exam_scores
    )
    SELECT student, COUNT(*) AS subjects
    FROM s
    WHERE score > subject_avg
    GROUP BY student
    ORDER BY student;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | student | subjects |
    | --- | --- |
    | Ava | 2 |
    | Ben | 1 |
    | Cleo | 3 |
    | Eli | 1 |
    <!-- /result -->

    Ava beat the average in math and art but not physics; Ben only in physics. Both slip in, with the wrong counts.

    **The correlated version, and why the window is better on a big table.** This also gives the right answer:

    <!-- sql -->
    ```sql
    SELECT e.student, COUNT(*) AS subjects
    FROM exam_scores e
    GROUP BY e.student
    HAVING COUNT(*) = SUM(CASE WHEN e.score > (SELECT AVG(x.score) FROM exam_scores x
                                              WHERE x.subject = e.subject) THEN 1 ELSE 0 END)
    ORDER BY e.student;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | student | subjects |
    | --- | --- |
    | Cleo | 3 |
    | Eli | 1 |
    <!-- /result -->

    but the inner `SELECT AVG(...)` can run once for every row. Timed in this course's test container on 200,000
    rows (2,000 students, 100 subjects, primary key on `(student, subject)`, so no index starting with `subject`),
    the window version took 0.13 s on PostgreSQL 16 and 0.17 s on SQLite 3.53. The correlated version had not
    finished after 2 minutes on either database, and was stopped. A hidden performance test would fail it. If you
    write a correlated subquery, ask whether a window function or a join to a grouped CTE can replace it.

### B.5 Active subscribers each month { #b5 }

**Level:** medium-hard · **Aim for:** 20 minutes

A subscription is active from `start_date` to `end_date`, **both included**; `end_date` is NULL while it is still
running. `report_months` lists the days to report on. For each of them, return `month_start`, `active_users` (users
with at least one subscription active that day) and `pro_users` (users with an active `pro` subscription that day).
Days with nobody active show 0. Sort by `month_start`.

<!-- sql setup -->
```sql
CREATE TABLE subscriptions (
  sub_id     INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL,
  plan       VARCHAR(10) NOT NULL,
  start_date DATE NOT NULL,
  end_date   DATE
);
CREATE TABLE report_months (month_start DATE PRIMARY KEY);
INSERT INTO subscriptions VALUES
  (1, 1, 'basic', '2025-12-15', '2026-02-10'),
  (2, 2, 'pro',   '2026-01-01', NULL),
  (3, 3, 'basic', '2026-02-01', '2026-02-28'),
  (4, 3, 'pro',   '2026-03-01', NULL),
  (5, 4, 'basic', '2026-04-15', '2026-05-01'),
  (6, 5, 'pro',   '2026-07-01', NULL);
INSERT INTO report_months VALUES
  ('2025-12-01'), ('2026-01-01'), ('2026-02-01'), ('2026-03-01'), ('2026-04-01'), ('2026-05-01'), ('2026-06-01');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| month_start | active_users | pro_users |
| --- | --- | --- |
| 2025-12-01 | 0 | 0 |
| 2026-01-01 | 2 | 1 |
| 2026-02-01 | 3 | 1 |
| 2026-03-01 | 2 | 2 |
| 2026-04-01 | 2 | 2 |
| 2026-05-01 | 3 | 2 |
| 2026-06-01 | 2 | 2 |
<!-- /expected -->

??? success "Answer"
    <!-- sql expect -->
    ```sql
    SELECT m.month_start,
           COUNT(DISTINCT s.user_id)                                   AS active_users,
           COUNT(DISTINCT CASE WHEN s.plan = 'pro' THEN s.user_id END) AS pro_users
    FROM report_months m
    LEFT JOIN subscriptions s
      ON s.start_date <= m.month_start
     AND (s.end_date IS NULL OR s.end_date >= m.month_start)
    GROUP BY m.month_start
    ORDER BY m.month_start;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 7 rows.</p>

    | month_start | active_users | pro_users |
    | --- | --- | --- |
    | 2025-12-01 | 0 | 0 |
    | 2026-01-01 | 2 | 1 |
    | 2026-02-01 | 3 | 1 |
    | 2026-03-01 | 2 | 2 |
    | 2026-04-01 | 2 | 2 |
    | 2026-05-01 | 3 | 2 |
    | 2026-06-01 | 2 | 2 |
    <!-- /result -->

    Three things decide it. **The overlap test**: active on day d means started on or before d and not ended before
    d, with NULL meaning "not ended", hence the `OR s.end_date IS NULL`. **The left join from the days**, so that
    December, with nobody active, still appears with 0. **`COUNT(DISTINCT user_id)`**, so a user with two active
    subscriptions counts once. User 5 starts in July, after every report day, and never appears.

    Dropping the `IS NULL` part is the usual slip: then every open-ended subscription disappears.

    <!-- sql -->
    ```sql
    SELECT m.month_start, COUNT(DISTINCT s.user_id) AS active_users
    FROM report_months m
    LEFT JOIN subscriptions s
      ON s.start_date <= m.month_start AND s.end_date >= m.month_start
    GROUP BY m.month_start
    ORDER BY m.month_start;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 7 rows.</p>

    | month_start | active_users |
    | --- | --- |
    | 2025-12-01 | 0 |
    | 2026-01-01 | 1 |
    | 2026-02-01 | 2 |
    | 2026-03-01 | 0 |
    | 2026-04-01 | 0 |
    | 2026-05-01 | 1 |
    | 2026-06-01 | 0 |
    <!-- /result -->

### B.6 Managers out-earned by their team { #b6 }

**Level:** medium · **Aim for:** 15 minutes

In `staff`, `manager_id` points to another row. Find the managers whose **direct reports' average salary** is higher
than their own salary. Return `manager`, `manager_salary`, `team_size`, `team_avg` (rounded to a whole number),
sorted by `manager`.

<!-- sql setup -->
```sql
CREATE TABLE staff (
  id         INTEGER PRIMARY KEY,
  name       VARCHAR(30) NOT NULL,
  manager_id INTEGER REFERENCES staff (id),
  salary     INTEGER NOT NULL
);
INSERT INTO staff VALUES
  (1, 'Iris', NULL, 150000),
  (2, 'Jon',  1,     90000),
  (3, 'Kai',  1,    160000),
  (4, 'Lea',  2,     95000),
  (5, 'Max',  2,     99000),
  (6, 'Noor', 3,    120000),
  (7, 'Omid', 2,     80000),
  (8, 'Pia',  3,    210000);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| manager | manager_salary | team_size | team_avg |
| --- | --- | --- | --- |
| Jon | 90000 | 3 | 91333 |
| Kai | 160000 | 2 | 165000 |
<!-- /expected -->

??? success "Answer"
    <!-- sql expect -->
    ```sql
    SELECT m.name             AS manager,
           m.salary           AS manager_salary,
           COUNT(*)           AS team_size,
           ROUND(AVG(e.salary), 0) AS team_avg
    FROM staff m
    JOIN staff e ON e.manager_id = m.id
    GROUP BY m.id, m.name, m.salary
    HAVING AVG(e.salary) > m.salary
    ORDER BY m.name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | manager | manager_salary | team_size | team_avg |
    | --- | --- | --- | --- |
    | Jon | 90000 | 3 | 91333 |
    | Kai | 160000 | 2 | 165000 |
    <!-- /result -->

    A self join: `m` is the manager, `e` each of their reports. Group by the manager's id (and the columns shown),
    then compare the group's average in `HAVING`. Jon's team averages 91,333 against his 90,000; Kai's 165,000
    against 160,000; Iris's team (Jon and Kai) averages 125,000, below her 150,000.

    The usual wrong answer compares each report with the manager, answering "managers with at least one report who
    earns more":

    <!-- sql -->
    ```sql
    SELECT DISTINCT m.name AS manager
    FROM staff m
    JOIN staff e ON e.manager_id = m.id
    WHERE e.salary > m.salary
    ORDER BY m.name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | manager |
    | --- |
    | Iris |
    | Jon |
    | Kai |
    <!-- /result -->

    Iris appears because Kai alone earns more than she does.

### B.7 Who talks to whom { #b7 }

**Level:** hard · **Aim for:** 25 minutes

Each row of `calls` is one call. For each person, return `person`, `total_minutes` (on calls they made **or**
received) and `top_contact`: the person they spent the most minutes with, counting calls in both directions. If two
contacts tie, take the one whose name comes first alphabetically. Sort by `person`.

<!-- sql setup -->
```sql
CREATE TABLE calls (
  call_id INTEGER PRIMARY KEY,
  caller  VARCHAR(10) NOT NULL,
  callee  VARCHAR(10) NOT NULL,
  minutes INTEGER NOT NULL
);
INSERT INTO calls VALUES
  (1, 'ana', 'bo',  10),
  (2, 'bo',  'ana',  5),
  (3, 'ana', 'cy',  25),
  (4, 'cy',  'dee', 20),
  (5, 'dee', 'ana',  3),
  (6, 'bo',  'cy',   7),
  (7, 'ana', 'bo',  10);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| person | total_minutes | top_contact |
| --- | --- | --- |
| ana | 53 | bo |
| bo | 32 | ana |
| cy | 52 | ana |
| dee | 23 | cy |
<!-- /expected -->

??? success "Answer"
    <!-- sql expect -->
    ```sql
    WITH legs AS (
      SELECT caller AS person, callee AS other, minutes FROM calls
      UNION ALL
      SELECT callee, caller, minutes FROM calls
    ),
    per_contact AS (
      SELECT person, other, SUM(minutes) AS minutes
      FROM legs
      GROUP BY person, other
    ),
    ranked AS (
      SELECT person, other,
             SUM(minutes) OVER (PARTITION BY person) AS total_minutes,
             ROW_NUMBER() OVER (PARTITION BY person ORDER BY minutes DESC, other) AS rn
      FROM per_contact
    )
    SELECT person, total_minutes, other AS top_contact
    FROM ranked
    WHERE rn = 1
    ORDER BY person;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | person | total_minutes | top_contact |
    | --- | --- | --- |
    | ana | 53 | bo |
    | bo | 32 | ana |
    | cy | 52 | ana |
    | dee | 23 | cy |
    <!-- /result -->

    The key step is `legs`: every call becomes two rows, one from each end, so "made or received" turns into a plain
    `GROUP BY person`. Ana spent 25 minutes with Bo (10 + 5 + 10) and 25 with Cy: a tie, settled by name, so Bo.

    Writing `UNION` instead of `UNION ALL` is the classic mistake. `UNION` removes duplicate rows, and calls 1 and 7
    are the same caller, callee and length:

    <!-- sql -->
    ```sql
    WITH legs AS (
      SELECT caller AS person, callee AS other, minutes FROM calls
      UNION
      SELECT callee, caller, minutes FROM calls
    )
    SELECT person, SUM(minutes) AS total_minutes
    FROM legs
    GROUP BY person
    ORDER BY person;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | person | total_minutes |
    | --- | --- |
    | ana | 43 |
    | bo | 22 |
    | cy | 52 |
    | dee | 23 |
    <!-- /result -->

    One of the two 10-minute calls between Ana and Bo vanished, so both of their totals are 10 short. Unless you
    want duplicates removed, use `UNION ALL` ([chapter 12](12-Set-Operations.md#union)).

### B.8 Sales by quarter, with the best quarter { #b8 }

**Level:** medium-hard · **Aim for:** 20 minutes

`quarterly_sales` may hold several rows for the same region and quarter. Return one row per region: `region`, `q1`,
`q2`, `q3`, `q4` (the total for each quarter, 0 when there were no sales), `total`, and `best_quarter` (the quarter
with the highest total; if two tie, the earlier one). Sort by `region`.

<!-- sql setup -->
```sql
CREATE TABLE quarterly_sales (
  region  VARCHAR(10) NOT NULL,
  quarter CHAR(2) NOT NULL,          -- 'Q1' to 'Q4'
  amount  NUMERIC(10,2) NOT NULL
);
INSERT INTO quarterly_sales VALUES
  ('North', 'Q1', 100), ('North', 'Q1',  50), ('North', 'Q2', 120), ('North', 'Q4',  90),
  ('South', 'Q2', 200), ('South', 'Q3', 200), ('South', 'Q4',  10),
  ('West',  'Q3',  75);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| region | q1 | q2 | q3 | q4 | total | best_quarter |
| --- | --- | --- | --- | --- | --- | --- |
| North | 150.00 | 120.00 | 0 | 90.00 | 360.00 | Q1 |
| South | 0 | 200.00 | 200.00 | 10.00 | 410.00 | Q2 |
| West | 0 | 0 | 75.00 | 0 | 75.00 | Q3 |
<!-- /expected -->

??? success "Answer"
    <!-- sql expect -->
    ```sql
    WITH per_quarter AS (
      SELECT region, quarter, SUM(amount) AS amount
      FROM quarterly_sales
      GROUP BY region, quarter
    ),
    best AS (
      SELECT region, quarter,
             ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC, quarter) AS rn
      FROM per_quarter
    )
    SELECT p.region,
           SUM(CASE WHEN p.quarter = 'Q1' THEN p.amount ELSE 0 END) AS q1,
           SUM(CASE WHEN p.quarter = 'Q2' THEN p.amount ELSE 0 END) AS q2,
           SUM(CASE WHEN p.quarter = 'Q3' THEN p.amount ELSE 0 END) AS q3,
           SUM(CASE WHEN p.quarter = 'Q4' THEN p.amount ELSE 0 END) AS q4,
           SUM(p.amount)                                           AS total,
           b.quarter                                               AS best_quarter
    FROM per_quarter p
    JOIN best b ON b.region = p.region AND b.rn = 1
    GROUP BY p.region, b.quarter
    ORDER BY p.region;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | region | q1 | q2 | q3 | q4 | total | best_quarter |
    | --- | --- | --- | --- | --- | --- | --- |
    | North | 150.00 | 120.00 | 0 | 90.00 | 360.00 | Q1 |
    | South | 0 | 200.00 | 200.00 | 10.00 | 410.00 | Q2 |
    | West | 0 | 0 | 75.00 | 0 | 75.00 | Q3 |
    <!-- /result -->

    Sum per region and quarter first: North has two Q1 rows (150 together), and judging the best quarter on single
    rows would compare 100 with 120 and pick Q2. Then pivot with `SUM(CASE ...)`, using `ELSE 0` so a missing quarter
    shows 0 rather than NULL. South's Q2 and Q3 tie at 200; `ORDER BY amount DESC, quarter` picks Q2, and the
    quarter names sort in calendar order because they are `Q1` to `Q4`. ([15.4 Pivot](15-Classic-Interview-Patterns.md#pivot).)

### B.9 Downtime periods { #b9 }

**Level:** hard · **Aim for:** 25 minutes

`machine_log` has one row per machine per hour, with `status` 'up' or 'down'. Return every unbroken period of
downtime: `machine`, `from_hour`, `to_hour`, `hours` (the length of the period). Sort by `machine`, then
`from_hour`.

<!-- sql setup -->
```sql
CREATE TABLE machine_log (
  machine VARCHAR(5) NOT NULL,
  hour    INTEGER NOT NULL,
  status  VARCHAR(4) NOT NULL,
  PRIMARY KEY (machine, hour)
);
INSERT INTO machine_log VALUES
  ('M1', 1, 'up'), ('M1', 2, 'down'), ('M1', 3, 'down'), ('M1', 4, 'up'), ('M1', 5, 'down'),
  ('M1', 6, 'up'), ('M1', 7, 'up'), ('M1', 8, 'down'), ('M1', 9, 'down'), ('M1', 10, 'down'),
  ('M2', 1, 'up'), ('M2', 2, 'up'), ('M2', 3, 'up'), ('M2', 4, 'down'), ('M2', 5, 'down'),
  ('M2', 6, 'down'), ('M2', 7, 'down'), ('M2', 8, 'up');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| machine | from_hour | to_hour | hours |
| --- | --- | --- | --- |
| M1 | 2 | 3 | 2 |
| M1 | 5 | 5 | 1 |
| M1 | 8 | 10 | 3 |
| M2 | 4 | 7 | 4 |
<!-- /expected -->

??? success "Answer"
    <!-- sql expect -->
    ```sql
    WITH down AS (
      SELECT machine, hour,
             hour - ROW_NUMBER() OVER (PARTITION BY machine ORDER BY hour) AS island
      FROM machine_log
      WHERE status = 'down'
    )
    SELECT machine, MIN(hour) AS from_hour, MAX(hour) AS to_hour, COUNT(*) AS hours
    FROM down
    GROUP BY machine, island
    ORDER BY machine, from_hour;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | machine | from_hour | to_hour | hours |
    | --- | --- | --- | --- |
    | M1 | 2 | 3 | 2 |
    | M1 | 5 | 5 | 1 |
    | M1 | 8 | 10 | 3 |
    | M2 | 4 | 7 | 4 |
    <!-- /result -->

    Gaps and islands ([15.3](15-Classic-Interview-Patterns.md#islands)). Keep only the 'down' hours and number them;
    within an unbroken run, hour and row number both go up by 1, so their difference stays the same, and that
    difference names the run. For M1 the down hours 2, 3, 5, 8, 9, 10 get numbers 1 to 6, differences 1, 1, 2, 4, 4,
    4: three runs. The trick needs one row per hour; if hours could be missing from the log, decide first whether a
    missing hour breaks a period, and say so.

    The same answer by flagging where each run starts, which also works when the steps are not evenly spaced (dates
    with gaps, timestamps):

    <!-- sql same -->
    ```sql
    WITH marked AS (
      SELECT machine, hour, status,
             CASE WHEN status = LAG(status) OVER (PARTITION BY machine ORDER BY hour) THEN 0 ELSE 1 END AS starts_run
      FROM machine_log
    ),
    numbered AS (
      SELECT machine, hour, status,
             SUM(starts_run) OVER (PARTITION BY machine ORDER BY hour ROWS UNBOUNDED PRECEDING) AS run_id
      FROM marked
    )
    SELECT machine, MIN(hour) AS from_hour, MAX(hour) AS to_hour, COUNT(*) AS hours
    FROM numbered
    WHERE status = 'down'
    GROUP BY machine, run_id
    ORDER BY machine, from_hour;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 4 rows.</p>

    | machine | from_hour | to_hour | hours |
    | --- | --- | --- | --- |
    | M1 | 2 | 3 | 2 |
    | M1 | 5 | 5 | 1 |
    | M1 | 8 | 10 | 3 |
    | M2 | 4 | 7 | 4 |
    <!-- /result -->

    The first row of each machine has no previous status, so `LAG` is NULL, the `=` is not true, and it starts a run:
    exactly what is wanted.

### B.10 History table from snapshots { #b10 }

**Level:** hard · **Aim for:** 30 minutes

`customer_snapshots` holds each customer's city as copied on the first of every month. Turn it into a history
table, one row per unbroken stretch in the same city: `customer_id`, `city`, `valid_from` (the first snapshot of the
stretch) and `valid_to` (the first snapshot of the next stretch, or NULL for the current one). Sort by
`customer_id`, then `valid_from`. (This is a "type 2 slowly changing dimension", a common data engineering table.)

<!-- sql setup -->
```sql
CREATE TABLE customer_snapshots (
  snapshot_date DATE NOT NULL,
  customer_id   INTEGER NOT NULL,
  city          VARCHAR(20) NOT NULL,
  PRIMARY KEY (snapshot_date, customer_id)
);
INSERT INTO customer_snapshots VALUES
  ('2026-01-01', 1, 'Oslo'),   ('2026-02-01', 1, 'Oslo'),   ('2026-03-01', 1, 'Bergen'),
  ('2026-04-01', 1, 'Bergen'), ('2026-05-01', 1, 'Oslo'),   ('2026-06-01', 1, 'Oslo'),
  ('2026-02-01', 2, 'Lima'),   ('2026-03-01', 2, 'Lima'),   ('2026-04-01', 2, 'Lima'),
  ('2026-05-01', 2, 'Lima'),   ('2026-06-01', 2, 'Lima'),
  ('2026-01-01', 3, 'Kyiv'),   ('2026-02-01', 3, 'Kyiv'),   ('2026-03-01', 3, 'Kyiv'),
  ('2026-04-01', 3, 'Riga'),   ('2026-05-01', 3, 'Kyiv'),   ('2026-06-01', 3, 'Kyiv');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| customer_id | city | valid_from | valid_to |
| --- | --- | --- | --- |
| 1 | Oslo | 2026-01-01 | 2026-03-01 |
| 1 | Bergen | 2026-03-01 | 2026-05-01 |
| 1 | Oslo | 2026-05-01 | *NULL* |
| 2 | Lima | 2026-02-01 | *NULL* |
| 3 | Kyiv | 2026-01-01 | 2026-04-01 |
| 3 | Riga | 2026-04-01 | 2026-05-01 |
| 3 | Kyiv | 2026-05-01 | *NULL* |
<!-- /expected -->

??? success "Answer"
    <!-- sql expect -->
    ```sql
    WITH marked AS (
      SELECT customer_id, snapshot_date, city,
             CASE WHEN city = LAG(city) OVER (PARTITION BY customer_id ORDER BY snapshot_date)
                  THEN 0 ELSE 1 END AS starts_stretch
      FROM customer_snapshots
    ),
    numbered AS (
      SELECT customer_id, snapshot_date, city,
             SUM(starts_stretch) OVER (PARTITION BY customer_id ORDER BY snapshot_date
                                       ROWS UNBOUNDED PRECEDING) AS stretch
      FROM marked
    ),
    stretches AS (
      SELECT customer_id, stretch, city, MIN(snapshot_date) AS valid_from
      FROM numbered
      GROUP BY customer_id, stretch, city
    )
    SELECT customer_id, city, valid_from,
           LEAD(valid_from) OVER (PARTITION BY customer_id ORDER BY valid_from) AS valid_to
    FROM stretches
    ORDER BY customer_id, valid_from;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 7 rows.</p>

    | customer_id | city | valid_from | valid_to |
    | --- | --- | --- | --- |
    | 1 | Oslo | 2026-01-01 | 2026-03-01 |
    | 1 | Bergen | 2026-03-01 | 2026-05-01 |
    | 1 | Oslo | 2026-05-01 | *NULL* |
    | 2 | Lima | 2026-02-01 | *NULL* |
    | 3 | Kyiv | 2026-01-01 | 2026-04-01 |
    | 3 | Riga | 2026-04-01 | 2026-05-01 |
    | 3 | Kyiv | 2026-05-01 | *NULL* |
    <!-- /result -->

    Mark each snapshot where the city differs from the one before, number the stretches with a running sum of the
    marks, take each stretch's first date, and let `LEAD` fetch the next stretch's start as the end. The usual wrong
    answer groups by city, which glues Oslo-Bergen-Oslo into two rows with overlapping dates:

    <!-- sql -->
    ```sql
    SELECT customer_id, city, MIN(snapshot_date) AS valid_from, MAX(snapshot_date) AS valid_to
    FROM customer_snapshots
    GROUP BY customer_id, city
    ORDER BY customer_id, valid_from;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | customer_id | city | valid_from | valid_to |
    | --- | --- | --- | --- |
    | 1 | Oslo | 2026-01-01 | 2026-06-01 |
    | 1 | Bergen | 2026-03-01 | 2026-04-01 |
    | 2 | Lima | 2026-02-01 | 2026-06-01 |
    | 3 | Kyiv | 2026-01-01 | 2026-06-01 |
    | 3 | Riga | 2026-04-01 | 2026-04-01 |
    <!-- /result -->

    Customer 1's first Oslo row runs from January to June, straight across the Bergen months. If `city` could be
    NULL, compare with `IS DISTINCT FROM` instead of `=` so that a change to or from NULL also starts a stretch
    ([6.3](06-Null-and-Three-Valued-Logic.md#is-null)). [Chapter 22](22-Duplicates-and-Incremental-Loads.md) builds the
    same table incrementally.

### B.11 Days to the second purchase { #b11 }

**Level:** medium-hard · **Aim for:** 20 minutes

For each customer who bought on at least two different days, return `customer`, `first_day` (their first purchase
day), `second_day` (the next day on which they bought) and `days_between`. Several purchases on the same day count
as one day. Sort by `days_between` from most to fewest, then by `customer`.

<!-- sql setup -->
```sql
CREATE TABLE purchases (
  purchase_id  INTEGER PRIMARY KEY,
  customer     VARCHAR(10) NOT NULL,
  purchased_on DATE NOT NULL,
  amount       NUMERIC(8,2) NOT NULL
);
INSERT INTO purchases VALUES
  (1, 'kim', '2026-01-05', 20.00), (2, 'kim', '2026-01-05', 15.00), (3, 'kim', '2026-01-20', 40.00),
  (4, 'lou', '2026-02-01', 12.00), (5, 'lou', '2026-03-03',  9.50),
  (6, 'max', '2026-01-10', 30.00),
  (7, 'nia', '2026-01-31',  5.00), (8, 'nia', '2026-02-01',  7.00), (9, 'nia', '2026-02-15', 11.00);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| customer | first_day | second_day | days_between |
| --- | --- | --- | --- |
| lou | 2026-02-01 | 2026-03-03 | 30 |
| kim | 2026-01-05 | 2026-01-20 | 15 |
| nia | 2026-01-31 | 2026-02-01 | 1 |
<!-- /expected -->

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg expect -->
        ```sql
        WITH days AS (
          SELECT DISTINCT customer, purchased_on FROM purchases
        ),
        numbered AS (
          SELECT customer, purchased_on,
                 ROW_NUMBER() OVER (PARTITION BY customer ORDER BY purchased_on) AS n
          FROM days
        )
        SELECT a.customer,
               a.purchased_on                  AS first_day,
               b.purchased_on                  AS second_day,
               b.purchased_on - a.purchased_on AS days_between
        FROM numbered a
        JOIN numbered b ON b.customer = a.customer AND b.n = 2
        WHERE a.n = 1
        ORDER BY days_between DESC, a.customer;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

        | customer | first_day | second_day | days_between |
        | --- | --- | --- | --- |
        | lou | 2026-02-01 | 2026-03-03 | 30 |
        | kim | 2026-01-05 | 2026-01-20 | 15 |
        | nia | 2026-01-31 | 2026-02-01 | 1 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        WITH days AS (
          SELECT DISTINCT customer, purchased_on FROM purchases
        ),
        numbered AS (
          SELECT customer, purchased_on,
                 ROW_NUMBER() OVER (PARTITION BY customer ORDER BY purchased_on) AS n
          FROM days
        )
        SELECT a.customer,
               a.purchased_on AS first_day,
               b.purchased_on AS second_day,
               CAST(julianday(b.purchased_on) - julianday(a.purchased_on) AS INTEGER) AS days_between
        FROM numbered a
        JOIN numbered b ON b.customer = a.customer AND b.n = 2
        WHERE a.n = 1
        ORDER BY days_between DESC, a.customer;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 3 rows.</p>

        | customer | first_day | second_day | days_between |
        | --- | --- | --- | --- |
        | lou | 2026-02-01 | 2026-03-03 | 30 |
        | kim | 2026-01-05 | 2026-01-20 | 15 |
        | nia | 2026-01-31 | 2026-02-01 | 1 |
        <!-- /result -->

    `DISTINCT` first turns purchases into purchase days; without it, Kim's two purchases on 5 January would be
    numbers 1 and 2, giving 0 days. The inner join to row 2 drops Max, who bought on only one day. `LEAD` works too:
    take `LEAD(purchased_on)` over the distinct days and keep row 1. From 1 February to 3 March 2026 is 30 days,
    because February 2026 has 28.

### B.12 Mutual follows { #b12 }

**Level:** easy-medium · **Aim for:** 10 minutes

`follows` has a row when `follower` follows `followee`. Return every pair of users who follow **each other**, each
pair once, as `user_a` and `user_b` with `user_a` before `user_b` alphabetically. Sort by `user_a`, then `user_b`.

<!-- sql setup -->
```sql
CREATE TABLE follows (
  follower VARCHAR(10) NOT NULL,
  followee VARCHAR(10) NOT NULL,
  PRIMARY KEY (follower, followee)
);
INSERT INTO follows VALUES
  ('ana', 'bo'), ('bo', 'ana'), ('ana', 'cy'), ('cy', 'dee'), ('dee', 'cy'),
  ('bo', 'cy'), ('eve', 'eve'), ('cy', 'ana');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| user_a | user_b |
| --- | --- |
| ana | bo |
| ana | cy |
| cy | dee |
<!-- /expected -->

??? success "Answer"
    <!-- sql expect -->
    ```sql
    SELECT f.follower AS user_a, f.followee AS user_b
    FROM follows f
    JOIN follows g
      ON g.follower = f.followee
     AND g.followee = f.follower
    WHERE f.follower < f.followee
    ORDER BY user_a, user_b;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | user_a | user_b |
    | --- | --- |
    | ana | bo |
    | ana | cy |
    | cy | dee |
    <!-- /result -->

    The self join finds the reverse row. `f.follower < f.followee` keeps each pair once, the right way round, and
    also removes Eve, who follows herself: her row is its own reverse. Without that line every pair appears twice and
    Eve once:

    <!-- sql -->
    ```sql
    SELECT f.follower AS user_a, f.followee AS user_b
    FROM follows f
    JOIN follows g ON g.follower = f.followee AND g.followee = f.follower
    ORDER BY user_a, user_b;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 7 rows.</p>

    | user_a | user_b |
    | --- | --- |
    | ana | bo |
    | ana | cy |
    | bo | ana |
    | cy | ana |
    | cy | dee |
    | dee | cy |
    | eve | eve |
    <!-- /result -->

## After this set { #next }

Sit the timed [mock tests](32-Mock-Tests.md) next, then the two mock tests in the [Codility test
prep](../../interview/codility/index.md) guide. Each task here names the chapter behind it; if one took far longer than
its time, that chapter is the one to reread.

**Next:** [32. Mock tests](32-Mock-Tests.md).
