# 32. Mock tests

*Two timed rehearsals, each with two SQL tasks on tables you have not seen before, written in the style of an online
coding test. Set a timer, write your answers in a real database, and only then open the solutions. Every solution
ran on PostgreSQL 16 and SQLite 3.53.*

!!! warning "What is known about the real test, and what is not"
    The format of the test you will be sent is **not known in advance**: the number of tasks, the time allowed and
    the SQL dialects are set by the employer and shown on the test's first page. What is verified: on Codility's own
    public practice SQL tasks (checked 11 Nov 2026), a task offers **SQL (PostgreSQL)** and **SQL (SQLite)**, and the
    result's column **order** matters while the column names do not. The [Codility test
    prep](../../interview/codility/index.md) guide explains how a Codility test works and has four more mock tests
    that include a Python task, starting with [mock test 1](../../interview/codility/mock-test-1.md).

!!! abstract "How to sit a mock"
    1. Give yourself **40 minutes for the two tasks** of one mock. Do not open any answer before the time is up.
    2. Load the task's tables into SQLite or PostgreSQL (the SQL is given), write the query, and check it against the
       "your query should return" table.
    3. Before you stop, add one or two rows of your own that the example does not cover (a NULL, a tie, a row with no
       match) and see whether your query still does what the task says. Hidden tests do this.
    4. Then open the solution, compare, and read the wrong answers: they are the ones markers see most.
    5. Score yourself: a task counts only if the rows, the columns and their order, and the sort are all exactly
       right.

## Mock test 1 { #mock-1 }

### Task 1: Late deliveries { #m1-t1 }

**Aim for:** 15 minutes

Each order promises delivery within `promised_days` days of `ordered_on`. An order is **late** if it was delivered
after `ordered_on + promised_days`, or if it has not been delivered (`delivered_on` is NULL) and that deadline is
before 1 June 2026, the day the report is run. For each customer, return `customer`, `orders`, `late_orders` and
`late_pct` (late orders as a percentage of all their orders, rounded to 1 decimal place). Sort by `late_pct` from
highest to lowest, then by `customer`.

<!-- sql setup -->
```sql
CREATE TABLE deliveries (
  order_id      INTEGER PRIMARY KEY,
  customer      VARCHAR(20) NOT NULL,
  ordered_on    DATE NOT NULL,
  promised_days INTEGER NOT NULL,
  delivered_on  DATE
);
INSERT INTO deliveries VALUES
  (1, 'Acme',    '2026-05-01', 3, '2026-05-04'),
  (2, 'Acme',    '2026-05-02', 3, '2026-05-06'),
  (3, 'Acme',    '2026-05-20', 5, NULL),
  (4, 'Birch',   '2026-05-10', 2, '2026-05-12'),
  (5, 'Birch',   '2026-05-28', 7, NULL),
  (6, 'Cobalt',  '2026-05-15', 1, '2026-05-20'),
  (7, 'Cobalt',  '2026-05-25', 3, NULL),
  (8, 'Dune',    '2026-05-30', 2, '2026-05-31');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| customer | orders | late_orders | late_pct |
| --- | --- | --- | --- |
| Cobalt | 2 | 2 | 100.0 |
| Acme | 3 | 2 | 66.7 |
| Birch | 2 | 0 | 0.0 |
| Dune | 1 | 0 | 0.0 |
<!-- /expected -->

??? success "Solution"
    === "PostgreSQL"

        <!-- sql pg expect -->
        ```sql
        SELECT customer,
               COUNT(*) AS orders,
               SUM(CASE
                     WHEN delivered_on > ordered_on + promised_days THEN 1
                     WHEN delivered_on IS NULL
                      AND ordered_on + promised_days < DATE '2026-06-01' THEN 1
                     ELSE 0
                   END) AS late_orders,
               ROUND(100.0 * SUM(CASE
                     WHEN delivered_on > ordered_on + promised_days THEN 1
                     WHEN delivered_on IS NULL
                      AND ordered_on + promised_days < DATE '2026-06-01' THEN 1
                     ELSE 0
                   END) / COUNT(*), 1) AS late_pct
        FROM deliveries
        GROUP BY customer
        ORDER BY late_pct DESC, customer;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

        | customer | orders | late_orders | late_pct |
        | --- | --- | --- | --- |
        | Cobalt | 2 | 2 | 100.0 |
        | Acme | 3 | 2 | 66.7 |
        | Birch | 2 | 0 | 0.0 |
        | Dune | 1 | 0 | 0.0 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        WITH d AS (
          SELECT customer, delivered_on,
                 date(ordered_on, '+' || promised_days || ' days') AS deadline
          FROM deliveries
        )
        SELECT customer,
               COUNT(*) AS orders,
               SUM(CASE WHEN delivered_on > deadline THEN 1
                        WHEN delivered_on IS NULL AND deadline < '2026-06-01' THEN 1
                        ELSE 0 END) AS late_orders,
               ROUND(100.0 * SUM(CASE WHEN delivered_on > deadline THEN 1
                                      WHEN delivered_on IS NULL AND deadline < '2026-06-01' THEN 1
                                      ELSE 0 END) / COUNT(*), 1) AS late_pct
        FROM d
        GROUP BY customer
        ORDER BY late_pct DESC, customer;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 4 rows.</p>

        | customer | orders | late_orders | late_pct |
        | --- | --- | --- | --- |
        | Cobalt | 2 | 2 | 100 |
        | Acme | 3 | 2 | 66.7 |
        | Birch | 2 | 0 | 0 |
        | Dune | 1 | 0 | 0 |
        <!-- /result -->

    **Why.** An order is late in two different ways, so the `CASE` has two `WHEN`s. The undelivered ones are the
    trap: `delivered_on > deadline` is UNKNOWN when `delivered_on` is NULL, so without the second `WHEN` order 3
    (deadline 25 May, still not delivered) and order 7 would count as on time. Order 5's deadline, 4 June, is after
    the report day, so it is not late yet. Computing the deadline once in a CTE (as in the SQLite tab) saves writing
    the `CASE` twice; the PostgreSQL tab writes it out to show it also works without one. On PostgreSQL a date plus
    a whole number is a date; on SQLite, `date(d, '+3 days')` does the same.

    **The wrong answer markers see most** counts only `delivered_on > deadline`:

    <!-- sql pg -->
    ```sql
    SELECT customer, COUNT(*) AS orders,
           SUM(CASE WHEN delivered_on > ordered_on + promised_days THEN 1 ELSE 0 END) AS late_orders
    FROM deliveries
    GROUP BY customer
    ORDER BY customer;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | customer | orders | late_orders |
    | --- | --- | --- |
    | Acme | 3 | 1 |
    | Birch | 2 | 0 |
    | Cobalt | 2 | 1 |
    | Dune | 1 | 0 |
    <!-- /result -->

    Acme shows 1 late order instead of 2, and Cobalt 1 instead of 2.

### Task 2: Shopping funnel { #m1-t2 }

**Aim for:** 25 minutes

`site_events` records what each user did and when. A user **viewed** if they have any `view`; **carted** if they
have a `cart` event later than their first `view`; **bought** if they have a `buy` event later than their first
such `cart`. Return one row: `viewed`, `carted`, `bought` (numbers of users) and `conversion_pct` (bought as a
percentage of viewed, rounded to 1 decimal place).

<!-- sql setup -->
```sql
CREATE TABLE site_events (
  user_id    INTEGER NOT NULL,
  event_time TIMESTAMP NOT NULL,
  event      VARCHAR(10) NOT NULL       -- 'view', 'cart' or 'buy'
);
INSERT INTO site_events VALUES
  (1, '2026-05-01 10:00:00', 'view'),
  (1, '2026-05-01 10:05:00', 'cart'),
  (1, '2026-05-01 10:09:00', 'buy'),
  (2, '2026-05-01 11:00:00', 'cart'),
  (2, '2026-05-01 11:02:00', 'view'),
  (2, '2026-05-01 11:30:00', 'buy'),
  (3, '2026-05-02 09:00:00', 'view'),
  (3, '2026-05-02 09:10:00', 'view'),
  (3, '2026-05-02 09:20:00', 'cart'),
  (4, '2026-05-02 12:00:00', 'view'),
  (5, '2026-05-03 08:00:00', 'view'),
  (5, '2026-05-03 08:01:00', 'cart'),
  (5, '2026-05-03 08:01:00', 'cart'),
  (5, '2026-05-04 18:00:00', 'buy'),
  (6, '2026-05-03 14:00:00', 'buy');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| viewed | carted | bought | conversion_pct |
| --- | --- | --- | --- |
| 5 | 3 | 2 | 40.0 |
<!-- /expected -->

??? success "Solution"
    <!-- sql expect -->
    ```sql
    WITH first_view AS (
      SELECT user_id, MIN(event_time) AS t_view
      FROM site_events
      WHERE event = 'view'
      GROUP BY user_id
    ),
    first_cart AS (
      SELECT v.user_id, MIN(e.event_time) AS t_cart
      FROM first_view v
      JOIN site_events e
        ON e.user_id = v.user_id AND e.event = 'cart' AND e.event_time > v.t_view
      GROUP BY v.user_id
    ),
    bought AS (
      SELECT DISTINCT c.user_id
      FROM first_cart c
      JOIN site_events e
        ON e.user_id = c.user_id AND e.event = 'buy' AND e.event_time > c.t_cart
    )
    SELECT (SELECT COUNT(*) FROM first_view) AS viewed,
           (SELECT COUNT(*) FROM first_cart) AS carted,
           (SELECT COUNT(*) FROM bought)     AS bought,
           ROUND(100.0 * (SELECT COUNT(*) FROM bought) / (SELECT COUNT(*) FROM first_view), 1) AS conversion_pct;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | viewed | carted | bought | conversion_pct |
    | --- | --- | --- | --- |
    | 5 | 3 | 2 | 40.0 |
    <!-- /result -->

    **Why.** Each step is a CTE with one row per user who reached it, and each step joins to the one before it with
    a time condition, so the order of events is enforced. User 2 carted **before** viewing, so they do not count as
    carted (and so not as bought either), even though they bought later. User 3 viewed twice and carted: one user.
    User 5's duplicated cart event does not matter because each step is one row per user (`MIN`, `DISTINCT`). User 6
    bought without viewing and is not in the funnel at all. Five viewers (users 1 to 5), three carts (users 1, 3 and
    5), two buyers (1 and 5): 40.0 percent.

    **The usual wrong answer** counts each event type without looking at the order:

    <!-- sql -->
    ```sql
    SELECT COUNT(DISTINCT CASE WHEN event = 'view' THEN user_id END) AS viewed,
           COUNT(DISTINCT CASE WHEN event = 'cart' THEN user_id END) AS carted,
           COUNT(DISTINCT CASE WHEN event = 'buy'  THEN user_id END) AS bought
    FROM site_events;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | viewed | carted | bought |
    | --- | --- | --- |
    | 5 | 4 | 4 |
    <!-- /result -->

    Users 2 and 6 are counted as buyers, so the "funnel" has as many buyers as carts. The task's word "later" is the
    whole point; whenever a task says "after", "then" or "later", the answer needs a time comparison.

## Mock test 2 { #mock-2 }

### Task 1: Grade point averages { #m2-t1 }

**Aim for:** 15 minutes

Letter grades are worth points: A = 4, B = 3, C = 2, D = 1, F = 0. A grade of `W` (withdrawn) is not counted at all.
For each student with **at least three counted grades**, return `student`, `courses` (counted grades), `gpa` (the
average points, rounded to 2 decimal places) and `gpa_rank` (1 for the highest GPA; equal GPAs share a rank, and the
next rank follows without a gap). Sort by `gpa_rank`, then `student`.

<!-- sql setup -->
```sql
CREATE TABLE grades (
  student VARCHAR(10) NOT NULL,
  course  VARCHAR(10) NOT NULL,
  grade   CHAR(1) NOT NULL,
  PRIMARY KEY (student, course)
);
INSERT INTO grades VALUES
  ('Amir', 'BIO', 'A'), ('Amir', 'CHE', 'B'), ('Amir', 'MAT', 'A'), ('Amir', 'PHY', 'W'),
  ('Bea',  'BIO', 'B'), ('Bea',  'CHE', 'B'), ('Bea',  'MAT', 'A'), ('Bea',  'HIS', 'B'),
  ('Cal',  'BIO', 'C'), ('Cal',  'MAT', 'F'), ('Cal',  'PHY', 'W'), ('Cal',  'HIS', 'W'),
  ('Dina', 'BIO', 'A'), ('Dina', 'MAT', 'B'), ('Dina', 'CHE', 'A'),
  ('Ezra', 'CHE', 'D'), ('Ezra', 'HIS', 'C'), ('Ezra', 'MAT', 'B');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| student | courses | gpa | gpa_rank |
| --- | --- | --- | --- |
| Amir | 3 | 3.67 | 1 |
| Dina | 3 | 3.67 | 1 |
| Bea | 4 | 3.25 | 2 |
| Ezra | 3 | 2.00 | 3 |
<!-- /expected -->

??? success "Solution"
    <!-- sql expect -->
    ```sql
    WITH points AS (
      SELECT student,
             CASE grade WHEN 'A' THEN 4 WHEN 'B' THEN 3 WHEN 'C' THEN 2 WHEN 'D' THEN 1 WHEN 'F' THEN 0 END AS pts
      FROM grades
      WHERE grade <> 'W'
    ),
    per_student AS (
      SELECT student, COUNT(*) AS courses, ROUND(AVG(1.0 * pts), 2) AS gpa
      FROM points
      GROUP BY student
      HAVING COUNT(*) >= 3
    )
    SELECT student, courses, gpa,
           DENSE_RANK() OVER (ORDER BY gpa DESC) AS gpa_rank
    FROM per_student
    ORDER BY gpa_rank, student;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | student | courses | gpa | gpa_rank |
    | --- | --- | --- | --- |
    | Amir | 3 | 3.67 | 1 |
    | Dina | 3 | 3.67 | 1 |
    | Bea | 4 | 3.25 | 2 |
    | Ezra | 3 | 2.00 | 3 |
    <!-- /result -->

    **Why.** Remove the withdrawals **before** counting, so they neither count as a course nor as 0 points; Cal has
    only two counted grades and drops out. `CASE` maps letters to points. "Share a rank, next rank without a gap" is
    `DENSE_RANK` ([13.3](13-Window-Functions-Ranking.md#ties)). Amir and Dina tie at 3.67 and share rank 1; Bea is 2.
    Ranking by the rounded GPA is what the task shows; ranking by the unrounded average could split two students
    whose GPAs only differ after the second decimal, so say which you chose if the task is not clear.

    **The usual wrong answer** maps `W` to NULL inside the `CASE` but forgets that `COUNT(*)` still counts the row:

    <!-- sql -->
    ```sql
    SELECT student, COUNT(*) AS courses,
           ROUND(AVG(1.0 * CASE grade WHEN 'A' THEN 4 WHEN 'B' THEN 3 WHEN 'C' THEN 2
                                      WHEN 'D' THEN 1 WHEN 'F' THEN 0 END), 2) AS gpa
    FROM grades
    GROUP BY student
    HAVING COUNT(*) >= 3
    ORDER BY student;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | student | courses | gpa |
    | --- | --- | --- |
    | Amir | 4 | 3.67 |
    | Bea | 4 | 3.25 |
    | Cal | 4 | 1.00 |
    | Dina | 3 | 3.67 |
    | Ezra | 3 | 2.00 |
    <!-- /result -->

    The averages are right (`AVG` skips the NULLs), but Amir shows 4 courses and Cal, with two real grades, is let
    in. `COUNT(pts)` instead of `COUNT(*)` would fix it.

### Task 2: Daily peaks from duplicated sensor loads { #m2-t2 }

**Aim for:** 25 minutes

A sensor feed is loaded in batches, and a reading can arrive in more than one batch, sometimes corrected. For each
`(sensor, read_at)`, only the row from the **latest** `load_id` counts. Using only those rows, return for each sensor
and day: `sensor`, `day` (as `YYYY-MM-DD`), `peak` (the highest value that day) and `change` (the peak minus the
same sensor's peak on its previous day with readings; NULL for its first day). Sort by `sensor`, then `day`.

<!-- sql setup -->
```sql
CREATE TABLE readings (
  load_id INTEGER NOT NULL,
  sensor  VARCHAR(5) NOT NULL,
  read_at TIMESTAMP NOT NULL,
  value   NUMERIC(6,1) NOT NULL
);
INSERT INTO readings VALUES
  (1, 'T1', '2026-05-01 08:00:00', 20.5),
  (1, 'T1', '2026-05-01 14:00:00', 24.0),
  (2, 'T1', '2026-05-01 14:00:00', 23.0),
  (2, 'T1', '2026-05-02 09:00:00', 22.0),
  (3, 'T1', '2026-05-02 15:00:00', 26.5),
  (3, 'T1', '2026-05-04 12:00:00', 25.0),
  (1, 'T2', '2026-05-01 10:00:00', 18.0),
  (2, 'T2', '2026-05-01 10:00:00', 18.0),
  (2, 'T2', '2026-05-02 10:00:00', 17.5),
  (4, 'T2', '2026-05-02 10:00:00', 19.5);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| sensor | day | peak | change |
| --- | --- | --- | --- |
| T1 | 2026-05-01 | 23.0 | *NULL* |
| T1 | 2026-05-02 | 26.5 | 3.5 |
| T1 | 2026-05-04 | 25.0 | -1.5 |
| T2 | 2026-05-01 | 18.0 | *NULL* |
| T2 | 2026-05-02 | 19.5 | 1.5 |
<!-- /expected -->

??? success "Solution"
    <!-- sql expect -->
    ```sql
    WITH latest AS (
      SELECT sensor, read_at, value,
             ROW_NUMBER() OVER (PARTITION BY sensor, read_at ORDER BY load_id DESC) AS rn
      FROM readings
    ),
    daily AS (
      SELECT sensor, SUBSTR(CAST(read_at AS TEXT), 1, 10) AS day, MAX(value) AS peak
      FROM latest
      WHERE rn = 1
      GROUP BY sensor, SUBSTR(CAST(read_at AS TEXT), 1, 10)
    )
    SELECT sensor, day, peak,
           peak - LAG(peak) OVER (PARTITION BY sensor ORDER BY day) AS change
    FROM daily
    ORDER BY sensor, day;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | sensor | day | peak | change |
    | --- | --- | --- | --- |
    | T1 | 2026-05-01 | 23.0 | *NULL* |
    | T1 | 2026-05-02 | 26.5 | 3.5 |
    | T1 | 2026-05-04 | 25.0 | -1.5 |
    | T2 | 2026-05-01 | 18.0 | *NULL* |
    | T2 | 2026-05-02 | 19.5 | 1.5 |
    <!-- /result -->

    **Why.** Three steps, each a CTE. **De-duplicate first**: number the copies of each reading, newest load first,
    and keep number 1. T1's 2 pm reading on 1 May was corrected from 24.0 to 23.0, so that day's peak is 23.0, not
    24.0; T2's reading on 2 May was corrected from 17.5 to 19.5. **Then aggregate** to one row per sensor and day.
    **Then compare** with `LAG` over that sensor's days. "Previous day with readings" means the previous row, which
    is why T1's 4 May is compared with 2 May (3 May has no readings). `SUBSTR(CAST(read_at AS TEXT), 1, 10)` gives
    the date part on both databases; PostgreSQL could also use `CAST(read_at AS DATE)`.

    **The usual wrong answer** takes the peak over all rows without de-duplicating:

    <!-- sql -->
    ```sql
    SELECT sensor, SUBSTR(CAST(read_at AS TEXT), 1, 10) AS day, MAX(value) AS peak
    FROM readings
    GROUP BY sensor, SUBSTR(CAST(read_at AS TEXT), 1, 10)
    ORDER BY sensor, day;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | sensor | day | peak |
    | --- | --- | --- |
    | T1 | 2026-05-01 | 24.0 |
    | T1 | 2026-05-02 | 26.5 |
    | T1 | 2026-05-04 | 25.0 |
    | T2 | 2026-05-01 | 18.0 |
    | T2 | 2026-05-02 | 19.5 |
    <!-- /result -->

    T1's 1 May shows 24.0, a value that was corrected away. In data engineering this order, **de-duplicate, then
    aggregate, then compare**, comes up constantly ([chapter 22](22-Duplicates-and-Incremental-Loads.md)).

## Score yourself { #score }

| Result | What it means | Next |
| --- | --- | --- |
| 4 of 4 tasks exactly right | Ready for the real test | The [Codility test prep](../../interview/codility/index.md) mock tests, for the Python task |
| 2 or 3 | Close: usually one edge case | Reread the wrong-answer box of each task you missed, then [practice set B](31-Practice-Set-B.md) |
| 0 or 1 | The patterns need more practice | [Which technique?](which-technique.md), then chapters 13 to 15 and [practice set A](30-Practice-Set-A.md) |

**Next:** Part III starts with [17. INSERT, UPDATE, DELETE, MERGE](17-Insert-Update-Delete-Merge.md).
