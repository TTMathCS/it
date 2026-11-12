# Full mock A: 3 tasks in 150 minutes

The first full rehearsal, for Saturday 14 November. It has the format of your test: **three tasks, 150 minutes, in one sitting, no pause.**
**Set a timer for 150 minutes** and do not open a solution until the timer ends.

| Task | Type | Level | Aim for |
|---|---|---|---|
| 1 | SQL | Medium | 35 minutes |
| 2 | SQL | Hard | 45 minutes |
| 3 | Python | Medium | 35 minutes |

Every SQL task here was tested on **PostgreSQL only** (`sql-postgres` in the test's language menu). The Python
tasks use the standard library only.

**How to take it.** Read all three tasks first (10 minutes) and start with the one you see the clearest path
for. Write each answer in a plain text editor or on paper, the way you would type it into Codility's editor.
When the timer ends, paste each answer into its **Try it here** box: Run checks it on the example, **Check** also
on the edge cases from the solution. Then open the solutions, including the wrong answers, and write down every
mistake you made.

Before you open a solution, write down the edge cases you thought of. Then compare with the list in the solution.

---

### Task&nbsp;1: Net revenue per category

**Level:** Medium · **Aim for:** 35 minutes

A shop records each sale (`qty` items at `unit_price` dollars each) and each refund. A sale can have **no refund,
one, or several** (a customer may return items one at a time); `refunds.sale_id` is the sale it belongs to. Every
`sales.product_id` exists in `products`, but a product's `category` can be `NULL`.

Write an SQL query (PostgreSQL) that returns one row for **each category that has at least one sale**, with four
columns:

* `category`: the category, or the text `'Unknown'` for products with no category (no real category is called
  `'Unknown'`);
* `gross`: the sum of `qty * unit_price` over the category's sales;
* `refunded`: the sum of the refunds of those sales (0 if none);
* `net`: `gross` minus `refunded`.

Sort by `net` from highest to lowest, then by `category` from A to Z.

**Tables**

```sql
CREATE TABLE products (
    id       INTEGER PRIMARY KEY,
    name     VARCHAR(40) NOT NULL,
    category VARCHAR(20)
);
CREATE TABLE sales (
    id         INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    sold_on    DATE NOT NULL,
    qty        INTEGER NOT NULL,
    unit_price INTEGER NOT NULL
);
CREATE TABLE refunds (
    id      INTEGER PRIMARY KEY,
    sale_id INTEGER NOT NULL,
    amount  INTEGER NOT NULL
);
```

**Example data**

`products`

| id | name | category |
|---|---|---|
| 1 | Rake | Garden |
| 2 | Pan | Kitchen |
| 3 | Kite | NULL |
| 4 | Hose | Garden |
| 5 | Drum | Toys |

`sales`

| id | product_id | sold_on | qty | unit_price |
|---|---|---|---|---|
| 1 | 1 | 2026-05-01 | 2 | 15 |
| 2 | 2 | 2026-05-01 | 1 | 40 |
| 3 | 3 | 2026-05-02 | 3 | 10 |
| 4 | 4 | 2026-05-02 | 1 | 25 |
| 5 | 2 | 2026-05-03 | 2 | 40 |
| 6 | 1 | 2026-05-03 | 1 | 15 |

`refunds`

| id | sale_id | amount |
|---|---|---|
| 1 | 1 | 15 |
| 2 | 1 | 15 |
| 3 | 5 | 40 |
| 4 | 3 | 10 |

**Your query should return**

| category | gross | refunded | net |
|---|---|---|---|
| Kitchen | 120 | 40 | 80 |
| Garden | 70 | 30 | 40 |
| Unknown | 30 | 10 | 20 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**
    
    ```sql
    WITH refund_per_sale AS (          -- 1. one row per sale, so the join below cannot multiply sales
        SELECT sale_id, SUM(amount) AS refunded
        FROM refunds
        GROUP BY sale_id
    ),
    sale_rows AS (                         -- 2. one row per sale, with its category and refund
        SELECT COALESCE(p.category, 'Unknown') AS category,
               s.qty * s.unit_price          AS gross,
               COALESCE(r.refunded, 0)       AS refunded
        FROM sales s
        JOIN products p              ON p.id = s.product_id
        LEFT JOIN refund_per_sale r  ON r.sale_id = s.id     -- LEFT: keep sales with no refund
    )
    SELECT category,
           SUM(gross)                 AS gross,
           SUM(refunded)              AS refunded,
           SUM(gross) - SUM(refunded) AS net
    FROM sale_rows
    GROUP BY category
    ORDER BY net DESC, category;
    ```
    
    **Why it works**
    
    * **The trap is fan-out.** Sale 1 in the example has two refunds. Join `refunds` straight to `sales` and sale 1
      appears twice, so its `qty * unit_price` is counted twice in `gross`. Summing the refunds **per sale first**
      (step 1) gives one row per sale, and then the join cannot multiply anything.
    * `LEFT JOIN` keeps sales that have no refund; `COALESCE(r.refunded, 0)` turns their missing refund into 0. With
      an inner join, those sales would vanish from `gross` too.
    * `COALESCE(p.category, 'Unknown')` before grouping puts every product with no category in one `'Unknown'` group.
    * A product with no sales never reaches `sale_rows`, so its category does not appear: the task asks only for
      categories with at least one sale.
    * The table is read once and every join is on a key, so it stays fast on large tables (the timing below is for
      200,000 sales and 50,000 refunds).
    
    **Tested on PostgreSQL 16.** Every case below gave exactly the expected rows, columns and order:
    
    * the example above;
    * edge case: no refunds at all;
    * edge case: a product with no sales;
    * edge case: two refunds on one sale of two items;
    * edge case: equal net, sorted by name;
    * edge case: empty tables;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.07 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: join refunds directly (fan-out doubles gross)"
    
        ```sql
        SELECT COALESCE(p.category, 'Unknown') AS category,
               SUM(s.qty * s.unit_price) AS gross,
               COALESCE(SUM(r.amount), 0) AS refunded,
               SUM(s.qty * s.unit_price) - COALESCE(SUM(r.amount), 0) AS net
        FROM sales s
        JOIN products p ON p.id = s.product_id
        LEFT JOIN refunds r ON r.sale_id = s.id
        GROUP BY 1
        ORDER BY net DESC, category;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.
    
    ??? failure "A common wrong answer: inner join to the refunds drops sales without one"
    
        ```sql
        WITH r AS (SELECT sale_id, SUM(amount) AS refunded FROM refunds GROUP BY sale_id)
        SELECT COALESCE(p.category, 'Unknown') AS category, SUM(s.qty * s.unit_price) AS gross,
               SUM(r.refunded) AS refunded, SUM(s.qty * s.unit_price) - SUM(r.refunded) AS net
        FROM sales s JOIN products p ON p.id = s.product_id JOIN r ON r.sale_id = s.id
        GROUP BY 1 ORDER BY net DESC, category;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.
    
    ??? failure "A common wrong answer: NULL category not replaced"
    
        ```sql
        WITH r AS (SELECT sale_id, SUM(amount) AS refunded FROM refunds GROUP BY sale_id)
        SELECT p.category, SUM(s.qty * s.unit_price) AS gross, SUM(COALESCE(r.refunded, 0)) AS refunded,
               SUM(s.qty * s.unit_price) - SUM(COALESCE(r.refunded, 0)) AS net
        FROM sales s JOIN products p ON p.id = s.product_id LEFT JOIN r ON r.sale_id = s.id
        GROUP BY p.category ORDER BY net DESC, p.category;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.



---

### Task&nbsp;2: Longest rising streak of each sensor

**Level:** Hard · **Aim for:** 45 minutes

Each sensor sends at most one reading a day; `(sensor_id, read_on)` is unique. Some days are missing.

A **rising streak** is a run of **consecutive calendar days**, at least two, where every day's `value` is
**strictly greater** than the day before's. A missing day ends a streak, and so does a value that is equal or lower.

Write an SQL query (PostgreSQL) that returns, for each sensor that has at least one rising streak, its **longest**
one: `sensor_id`, `run_start` (first day), `run_end` (last day) and `days` (how many days it covers). If two streaks
of a sensor are equally long, return the earlier one. Sort by `sensor_id`.

**Tables**

```sql
CREATE TABLE readings (
    sensor_id INTEGER NOT NULL,
    read_on   DATE NOT NULL,
    value     INTEGER NOT NULL
);
```

**Example data**

`readings`

| sensor_id | read_on | value |
|---|---|---|
| 1 | 2026-03-01 | 5 |
| 1 | 2026-03-02 | 6 |
| 1 | 2026-03-03 | 9 |
| 1 | 2026-03-04 | 9 |
| 1 | 2026-03-05 | 10 |
| 1 | 2026-03-06 | 12 |
| 1 | 2026-03-07 | 13 |
| 2 | 2026-03-01 | 1 |
| 2 | 2026-03-02 | 3 |
| 2 | 2026-03-04 | 4 |
| 2 | 2026-03-05 | 8 |
| 3 | 2026-03-01 | 7 |
| 3 | 2026-03-02 | 6 |
| 3 | 2026-03-03 | 5 |

**Your query should return**

| sensor_id | run_start | run_end | days |
|---|---|---|---|
| 1 | 2026-03-04 | 2026-03-07 | 4 |
| 2 | 2026-03-01 | 2026-03-02 | 2 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**
    
    ```sql
    WITH marked AS (                -- 1. does this day continue the streak of the day before?
        SELECT sensor_id, read_on, value,
               CASE WHEN LAG(read_on) OVER w = read_on - 1      -- the day before exists
                     AND LAG(value)   OVER w < value            -- and was lower
                    THEN 0 ELSE 1 END AS starts_new
        FROM readings
        WINDOW w AS (PARTITION BY sensor_id ORDER BY read_on)
    ),
    grouped AS (                           -- 2. a running count of starts numbers the streaks
        SELECT *, SUM(starts_new) OVER (PARTITION BY sensor_id ORDER BY read_on) AS streak_no
        FROM marked
    ),
    streaks AS (                           -- 3. one row per streak of two days or more
        SELECT sensor_id, streak_no, MIN(read_on) AS run_start, MAX(read_on) AS run_end, COUNT(*) AS days
        FROM grouped
        GROUP BY sensor_id, streak_no
        HAVING COUNT(*) >= 2
    ),
    ranked AS (                            -- 4. the longest per sensor, the earliest on a tie
        SELECT *, ROW_NUMBER() OVER (PARTITION BY sensor_id ORDER BY days DESC, run_start) AS rn
        FROM streaks
    )
    SELECT sensor_id, run_start, run_end, days
    FROM ranked
    WHERE rn = 1
    ORDER BY sensor_id;
    ```
    
    **Why it works**
    
    This is **gaps and islands** with two conditions, built in four small steps (run each one on its own while you
    write it):
    
    1. With `LAG`, look at the previous reading of the same sensor. The day **continues** a streak only if the previous
       reading is from the day before (`read_on - 1`: in PostgreSQL, a date minus an integer is a date) **and** its value
       was lower. Otherwise this day **starts** a new group (`1`). The first reading has no previous one: `LAG` gives
       `NULL`, the comparison is not true, and it starts a group, as it should.
    2. A running `SUM` of those 1s numbers the groups: every day of one streak gets the same number.
    3. `GROUP BY` the number gives each streak's first day, last day and length; `HAVING COUNT(*) >= 2` drops single
       days, which are not streaks.
    4. `ROW_NUMBER` ordered by length (longest first) and then start (earliest first) picks one streak per sensor,
       including the tie rule.
    
    In the example, sensor 1 has a streak 1 to 3 March (5, 6, 9), then 9 is not above 9, so a new streak runs 4 to 7
    March (9, 10, 12, 13): four days, the longest. Sensor 2 is missing 3 March, which splits its readings into two
    streaks of two days; the earlier wins. Sensor 3 only falls, so it has no row.
    
    The `WINDOW w AS (...)` clause names a window once so two `LAG` calls can share it; writing the `OVER (...)` out
    twice is the same.
    
    **Tested on PostgreSQL 16.** Every case below gave exactly the expected rows, columns and order:
    
    * the example above;
    * edge case: a missing day ends a streak;
    * edge case: equal values are not rising;
    * edge case: one reading only;
    * edge case: streak across a month end;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.24 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: a missing day does not end the streak (LAG of the value only)"
    
        ```sql
        WITH m AS (
            SELECT sensor_id, read_on, value,
                   CASE WHEN LAG(value) OVER (PARTITION BY sensor_id ORDER BY read_on) < value THEN 0 ELSE 1 END AS s
            FROM readings),
        g AS (SELECT *, SUM(s) OVER (PARTITION BY sensor_id ORDER BY read_on) AS k FROM m),
        t AS (SELECT sensor_id, k, MIN(read_on) AS run_start, MAX(read_on) AS run_end, COUNT(*) AS days
              FROM g GROUP BY sensor_id, k HAVING COUNT(*) >= 2),
        r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY sensor_id ORDER BY days DESC, run_start) AS rn FROM t)
        SELECT sensor_id, run_start, run_end, days FROM r WHERE rn = 1 ORDER BY sensor_id;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.
    
    ??? failure "A common wrong answer: <= instead of < (equal values counted as rising)"
    
        ```sql
        WITH m AS (
            SELECT sensor_id, read_on, value,
                   CASE WHEN LAG(read_on) OVER w = read_on - 1 AND LAG(value) OVER w <= value THEN 0 ELSE 1 END AS s
            FROM readings WINDOW w AS (PARTITION BY sensor_id ORDER BY read_on)),
        g AS (SELECT *, SUM(s) OVER (PARTITION BY sensor_id ORDER BY read_on) AS k FROM m),
        t AS (SELECT sensor_id, k, MIN(read_on) AS run_start, MAX(read_on) AS run_end, COUNT(*) AS days
              FROM g GROUP BY sensor_id, k HAVING COUNT(*) >= 2),
        r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY sensor_id ORDER BY days DESC, run_start) AS rn FROM t)
        SELECT sensor_id, run_start, run_end, days FROM r WHERE rn = 1 ORDER BY sensor_id;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.
    
    ??? failure "A common wrong answer: the tie goes to the later streak"
    
        ```sql
        WITH m AS (
            SELECT sensor_id, read_on, value,
                   CASE WHEN LAG(read_on) OVER w = read_on - 1 AND LAG(value) OVER w < value THEN 0 ELSE 1 END AS s
            FROM readings WINDOW w AS (PARTITION BY sensor_id ORDER BY read_on)),
        g AS (SELECT *, SUM(s) OVER (PARTITION BY sensor_id ORDER BY read_on) AS k FROM m),
        t AS (SELECT sensor_id, k, MIN(read_on) AS run_start, MAX(read_on) AS run_end, COUNT(*) AS days
              FROM g GROUP BY sensor_id, k HAVING COUNT(*) >= 2),
        r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY sensor_id ORDER BY days DESC, run_start DESC) AS rn FROM t)
        SELECT sensor_id, run_start, run_end, days FROM r WHERE rn = 1 ORDER BY sensor_id;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.



---

### Task&nbsp;3: Longest quiet time

**Level:** Medium · **Aim for:** 35 minutes

A database server runs batch jobs during a day that lasts `T` seconds, from second `0` to second `T`. Job `i`
keeps the server busy from second `S[i]` up to second `E[i]`: it is busy at moment `S[i]` and free again at moment
`E[i]`. Jobs may overlap, and they are listed in no particular order.

The team wants the longest stretch of time inside the day when **no job is running**, to plan a backup. Return its
length in seconds. If the server is busy for the whole day, return `0`; if there are no jobs, the whole day is
quiet.

**Examples**

* `solution(10, [1, 6], [3, 8])` returns `3`
* `solution(24, [2, 4, 5, 15], [6, 5, 9, 20])` returns `6`
* `solution(5, [], [])` returns `5`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `S` and `E`, is an integer within the range [0..100,000];
* `T` is an integer within the range [1..1,000,000,000];
* `0 ≤ S[i] < E[i] ≤ T` for every job.

Start from:

```python
def solution(T, S, E):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(T, S, E):
        best = 0
        busy_until = 0                       # the latest end seen so far
        for s, e in sorted(zip(S, E)):       # jobs in order of their start
            best = max(best, s - busy_until) # quiet from busy_until up to s (negative if they overlap)
            busy_until = max(busy_until, e)  # a short job inside a long one must not shrink this
        return max(best, T - busy_until)     # the quiet time after the last job
    ```
    
    **Why it works**
    
    * This is the **merge intervals** pattern again. Sort the jobs by start; keep `busy_until`, the moment the server
      is free again if no new job starts. Each new job either starts after `busy_until` (a quiet stretch of
      `s - busy_until` seconds) or overlaps what came before (no quiet time).
    * `busy_until = max(busy_until, e)`, not `busy_until = e`: a short job that sits inside a long job ends earlier,
      and taking its end would invent a quiet stretch that is not there (edge case "a job inside a longer job").
    * Two quiet stretches are easy to forget: the one **before the first job** (handled because `busy_until` starts at
      0) and the one **after the last job**, `T - busy_until`.
    * Jobs that touch (`E[i] == S[j]`) leave a gap of 0, which never beats `best`. With no jobs at all, the loop does
      nothing and the answer is `T`.
    * The plain answer marks every second of the day. It is right, but `T` can be a billion seconds: too slow and far
      too much memory. The sort works on the `N` jobs, not on the seconds.
    
    **Cost:** O(N log N) time for the sort, O(N) memory.
    
    **The slow answer:** Marking every second of the day: O(T) time and memory, and T can be a billion.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, busy all day: `solution(10, [0, 4], [6, 10])` returns `0`;
    * edge case, a job inside a longer job: `solution(20, [1, 2, 12], [10, 4, 14])` returns `6`;
    * edge case, jobs that touch leave no gap: `solution(9, [0, 3, 6], [3, 6, 9])` returns `0`;
    * edge case, the quiet time is at the start: `solution(100, [90], [95])` returns `90`;
    * edge case, the quiet time is at the end: `solution(100, [0], [5])` returns `95`;
    * edge case, the same job twice: `solution(10, [4, 4], [6, 6])` returns `4`;
    * edge case, jobs listed out of order: `solution(10, [6, 1], [8, 3])` returns `3`;
    * 800 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.086s.
    
    ??? failure "A common wrong answer: forgetting the quiet time after the last job"
    
        ```python
        def solution(T, S, E):
            best = 0
            busy_until = 0
            for s, e in sorted(zip(S, E)):
                best = max(best, s - busy_until)
                busy_until = max(busy_until, e)
            return best
        ```
        
        Checked: example: got 0 want 5.
    
    ??? failure "A common wrong answer: taking the end of the last job instead of the latest end"
    
        ```python
        def solution(T, S, E):
            best = 0
            busy_until = 0
            for s, e in sorted(zip(S, E)):
                best = max(best, s - busy_until)
                busy_until = e
            return max(best, T - busy_until)
        ```
        
        Checked: edge: a job inside a longer job: got 8 want 6.
    
    ??? failure "A common wrong answer: not sorting: the jobs come in no particular order"
    
        ```python
        def solution(T, S, E):
            best = 0
            busy_until = 0
            for s, e in zip(S, E):
                best = max(best, s - busy_until)
                busy_until = max(busy_until, e)
            return max(best, T - busy_until)
        ```
        
        Checked: edge: jobs listed out of order: got 6 want 3.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(T, S, E):
            busy = [False] * T                   # one flag per second of the day
            for s, e in zip(S, E):
                for t in range(s, e):
                    busy[t] = True
            best = run = 0
            for b in busy:
                run = 0 if b else run + 1
                best = max(best, run)
            return best
        ```
        
        It gives the right answers (the random tests compare against it), but it ran out of memory on the largest input.



---

## After the mock

Count your score as Codility would: for each task, the share of edge cases your answer got right. Then
spend an hour on the solutions and your mistakes list. Task 1 is about **aggregating before you join**, task 2
about **gaps and islands**, task 3 about **merging intervals**: if one of them went badly, the matching group of
the [SQL practice set](sql-practice.md) or [Python practice set](python-practice.md) is the place to go next.
Tomorrow: [Full mock B](full-mock-b.md).
