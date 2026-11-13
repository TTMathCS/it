# 15. Classic interview patterns

*A small number of question shapes make up most SQL test questions. Once you recognise the shape, the query almost
writes itself. This chapter collects them, each with a worked answer on the sample data and the wrong answer people
usually give: the Nth highest value, duplicates, the latest row per key, streaks of consecutive days (gaps and
islands), pivots, the median, "in every month", and "bought together".*

!!! abstract "In this chapter"
    **You will learn the patterns:**

    - Nth highest, four ways, including the one that must return NULL when there is no Nth
    - finding duplicates
    - consecutive days and streaks (gaps and islands)
    - pivot: rows into columns
    - the median, in both dialects
    - "every month" and other "for all" questions
    - pairs that occur together (market basket)

    **You need:** chapters 7 to 14, from [7. GROUP BY](07-Aggregation-Group-By-Having.md) to [14. LAG, LEAD, running totals](14-Window-Functions-Lag-Lead-Running-Totals.md). Each pattern names the chapter it builds on.

## 15.1 The Nth highest { #nth-highest }

"The second-highest salary." Four ways; the first is the one to reach for.

**1. DENSE_RANK** (chapter 13): rank the salary levels, keep level N.

**Task:** Find the second-highest different salary, as `second_highest`.

??? success "Solution"

    <!-- sql -->
    ```sql
    WITH levels AS (
      SELECT DISTINCT salary, DENSE_RANK() OVER (ORDER BY salary DESC) AS dr
      FROM employees
      WHERE salary IS NOT NULL
    )
    SELECT salary AS second_highest FROM levels WHERE dr = 2;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | second_highest |
    | --- |
    | 140000 |
    <!-- /result -->

**2. The largest below the largest** (only for N = 2):

<!-- sql same -->
```sql
SELECT MAX(salary) AS second_highest
FROM employees
WHERE salary < (SELECT MAX(salary) FROM employees);
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 1 row.</p>

| second_highest |
| --- |
| 140000 |
<!-- /result -->

**3. DISTINCT with LIMIT and OFFSET**: sort the different salaries, skip N − 1, take one.

<!-- sql same -->
```sql
SELECT DISTINCT salary AS second_highest
FROM employees
WHERE salary IS NOT NULL
ORDER BY salary DESC
LIMIT 1 OFFSET 1;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 1 row.</p>

| second_highest |
| --- |
| 140000 |
<!-- /result -->

**4. Correlated count**: a salary that exactly N − 1 different salaries are above.

<!-- sql same -->
```sql
SELECT DISTINCT e.salary AS second_highest
FROM employees e
WHERE (SELECT COUNT(DISTINCT x.salary) FROM employees x WHERE x.salary > e.salary) = 1;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 1 row.</p>

| second_highest |
| --- |
| 140000 |
<!-- /result -->

!!! failure "The usual wrong answer: no DISTINCT"
    <!-- sql -->
    ```sql
    SELECT salary AS third_highest
    FROM employees
    WHERE salary IS NOT NULL
    ORDER BY salary DESC
    LIMIT 1 OFFSET 2;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | third_highest |
    | --- |
    | 120000 |
    <!-- /result -->

    The third-highest **salary** is 110,000 (after 180,000 and 140,000). Without DISTINCT the two people on
    120,000 take places 3 and 4, and OFFSET 2 lands on one of them. "Third highest salary" means the third different
    value.

**When there is no Nth.** A well-known variant says: "if there is no second-highest salary, return NULL". The queries
above return **no row** in that case, which is not the same thing. Wrap the query as a scalar subquery: a scalar
subquery with no row gives NULL (chapter 10). Here, asking for the 10th-highest of the 9 salary levels:

**Task:** Find the 10th-highest different salary, giving NULL when there is no such salary.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT (
      SELECT DISTINCT salary FROM employees
      WHERE salary IS NOT NULL
      ORDER BY salary DESC
      LIMIT 1 OFFSET 9
    ) AS tenth_highest;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | tenth_highest |
    | --- |
    | *NULL* |
    <!-- /result -->

One row, holding NULL. The `SELECT MAX(...) WHERE salary < (SELECT MAX ...)` version (way 2) also returns NULL
rather than nothing, because an aggregate over no rows gives one row with NULL.

## 15.2 Duplicates { #duplicates }

**Finding them** is a GROUP BY on the columns that should be unique, keeping groups with more than one row:

**Task:** Find the (customer, login date) pairs that appear more than once in `logins`, with how many copies.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT customer_id, login_date, COUNT(*) AS copies
    FROM logins
    GROUP BY customer_id, login_date
    HAVING COUNT(*) > 1;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | customer_id | login_date | copies |
    | --- | --- | --- |
    | 2 | 2026-03-02 | 2 |
    <!-- /result -->

To see **every** duplicated row with its other columns, count with a window instead, so the rows are kept:

**Task:** List every customer whose name is shared with another customer: id, name and city, by id.

??? success "Solution"

    <!-- sql -->
    ```sql
    WITH c AS (
      SELECT customer_id, name, city,
             COUNT(*) OVER (PARTITION BY name) AS same_name
      FROM customers
    )
    SELECT customer_id, name, city FROM c WHERE same_name > 1 ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | customer_id | name | city |
    | --- | --- | --- |
    | 1 | Ana Silva | Toronto |
    | 10 | Ana Silva | Lisbon |
    <!-- /result -->

Two customers called Ana Silva, in different cities: "duplicate" depends on which columns you compare. Removing
duplicates (keep one, delete the rest) is in [chapter 22](22-Duplicates-and-Incremental-Loads.md).

## 15.3 Consecutive days: gaps and islands { #islands }

"The longest run of consecutive login days for each customer." This is the **gaps and islands** problem: each run of
consecutive days is an island, separated by gaps.

The trick: number each customer's login days 1, 2, 3, ... in date order, and subtract that number (as days) from the
date. Within a run of consecutive days, the date goes up by one and the number goes up by one, so the difference stays
**the same**. When there is a gap, the date jumps ahead and the difference changes. The difference labels the island.

**First remove duplicate days**, or a second login on the same day takes a number and breaks the run. Customer 2
logged in twice on 2 March.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    WITH days AS (
      SELECT DISTINCT customer_id, login_date FROM logins
    ),
    numbered AS (
      SELECT customer_id, login_date,
             login_date - CAST(ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY login_date) AS INTEGER) AS island
      FROM days
    )
    SELECT customer_id, MIN(login_date) AS run_start, MAX(login_date) AS run_end, COUNT(*) AS days
    FROM numbered
    GROUP BY customer_id, island
    ORDER BY customer_id, run_start;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 7 rows.</p>

    | customer_id | run_start | run_end | days |
    | --- | --- | --- | --- |
    | 1 | 2026-03-01 | 2026-03-03 | 3 |
    | 1 | 2026-03-05 | 2026-03-06 | 2 |
    | 1 | 2026-03-10 | 2026-03-10 | 1 |
    | 2 | 2026-03-01 | 2026-03-02 | 2 |
    | 2 | 2026-03-04 | 2026-03-04 | 1 |
    | 4 | 2026-03-03 | 2026-03-06 | 4 |
    | 6 | 2026-03-08 | 2026-03-08 | 1 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    WITH days AS (
      SELECT DISTINCT customer_id, login_date FROM logins
    ),
    numbered AS (
      SELECT customer_id, login_date,
             date(login_date, '-' || ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY login_date) || ' days') AS island
      FROM days
    )
    SELECT customer_id, MIN(login_date) AS run_start, MAX(login_date) AS run_end, COUNT(*) AS days
    FROM numbered
    GROUP BY customer_id, island
    ORDER BY customer_id, run_start;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 7 rows.</p>

    | customer_id | run_start | run_end | days |
    | --- | --- | --- | --- |
    | 1 | 2026-03-01 | 2026-03-03 | 3 |
    | 1 | 2026-03-05 | 2026-03-06 | 2 |
    | 1 | 2026-03-10 | 2026-03-10 | 1 |
    | 2 | 2026-03-01 | 2026-03-02 | 2 |
    | 2 | 2026-03-04 | 2026-03-04 | 1 |
    | 4 | 2026-03-03 | 2026-03-06 | 4 |
    | 6 | 2026-03-08 | 2026-03-08 | 1 |
    <!-- /result -->

Customer 1 has three islands (1–3 March, 5–6 March, 10 March); customer 4 one island of four days. The longest
streak per customer is then one more GROUP BY (`MAX(days)`), or "customers with a streak of at least 3 days" a
HAVING.

!!! failure "The usual wrong answer: forgetting the duplicate"
    <!-- sql pg -->
    ```sql
    WITH numbered AS (
      SELECT customer_id, login_date,
             login_date - CAST(ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY login_date) AS INTEGER) AS island
      FROM logins
      WHERE customer_id = 2
    )
    SELECT customer_id, MIN(login_date) AS run_start, MAX(login_date) AS run_end, COUNT(*) AS days
    FROM numbered
    GROUP BY customer_id, island
    ORDER BY run_start;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | customer_id | run_start | run_end | days |
    | --- | --- | --- | --- |
    | 2 | 2026-03-01 | 2026-03-04 | 3 |
    | 2 | 2026-03-02 | 2026-03-02 | 1 |
    <!-- /result -->

    Customer 2 logged in on 1, 2 and 4 March: a run of 2 days, then 1 day. Without DISTINCT the two 2 March rows
    get numbers 2 and 3, so every key after them shifts by one. 1 March, the first 2 March and 4 March land in one
    "island" from 1 to 4 March, counted as 3 days, with the gap on 3 March swallowed; the second 2 March row makes
    an island of its own. Both answers are wrong.

The same trick works on whole numbers (ids, sequence numbers): `id - ROW_NUMBER()` labels runs of consecutive ids,
which finds **gaps** in a sequence: wherever one island ends and the next starts.

## 15.4 Pivot: rows into columns { #pivot }

"Revenue per month, with one column per category." The data has one row per (month, category); the answer wants
months down the side and categories across the top. Put a CASE inside each SUM, one per output column:

**Task:** For each month, show revenue by category in columns (home, kitchen, office) and the total, one row per month.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT SUBSTR(CAST(o.order_date AS TEXT), 1, 7) AS month,
           SUM(CASE WHEN p.category = 'Home'    THEN i.quantity * i.unit_price ELSE 0 END) AS home,
           SUM(CASE WHEN p.category = 'Kitchen' THEN i.quantity * i.unit_price ELSE 0 END) AS kitchen,
           SUM(CASE WHEN p.category = 'Office'  THEN i.quantity * i.unit_price ELSE 0 END) AS office,
           SUM(i.quantity * i.unit_price) AS total
    FROM orders o
    JOIN order_items i ON i.order_id = o.order_id
    JOIN products p    ON p.product_id = i.product_id
    WHERE o.status = 'shipped'
    GROUP BY SUBSTR(CAST(o.order_date AS TEXT), 1, 7)
    ORDER BY month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | month | home | kitchen | office | total |
    | --- | --- | --- | --- | --- |
    | 2026-01 | 24.50 | 17.50 | 199.50 | 241.50 |
    | 2026-02 | 98.00 | 65.00 | 64.50 | 277.50 |
    | 2026-03 | 49.00 | 58.25 | 215.25 | 322.50 |
    | 2026-04 | 24.50 | 0 | 139.00 | 163.50 |
    <!-- /result -->

The `ELSE 0` makes an empty cell 0; leave it out and an empty cell is NULL. The `total` includes the gift card,
which has no category column of its own, so the three columns don't add up to it in February: check your columns
against the total to catch rows that fall through. SQL Server and Oracle also have a `PIVOT` keyword; PostgreSQL and
SQLite don't, and the CASE form works everywhere, so learn that.

## 15.5 The median { #median }

PostgreSQL has an ordered-set aggregate for it; SQLite (as normally built) doesn't, so it needs window functions.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT department,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary) AS median_salary
    FROM employees
    WHERE salary IS NOT NULL
    GROUP BY department
    ORDER BY department;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | department | median_salary |
    | --- | --- |
    | Engineering | 120000 |
    | Management | 180000 |
    | Sales | 70000 |
    | Support | 63500 |
    <!-- /result -->

=== "Both (window functions)"

    <!-- sql same -->
    ```sql
    WITH r AS (
      SELECT department, salary,
             ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary) AS rn,
             COUNT(*)     OVER (PARTITION BY department)                 AS n
      FROM employees
      WHERE salary IS NOT NULL
    )
    SELECT department, AVG(salary) AS median_salary
    FROM r
    WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
    GROUP BY department
    ORDER BY department;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 4 rows.</p>

    | department | median_salary |
    | --- | --- |
    | Engineering | 120000.000000000000 |
    | Management | 180000.000000000000 |
    | Sales | 70000.000000000000 |
    | Support | 63500.000000000000 |
    <!-- /result -->

The window version keeps the middle row (odd count) or the middle two (even count) and averages them. With whole
number division, `(n + 1) / 2` and `(n + 2) / 2` are the same row when `n` is odd and the two middle rows when `n` is
even. Ties in salary don't matter here: tied rows have the same value. `PERCENTILE_CONT` interpolates in the same way;
`PERCENTILE_DISC(0.5)` would return an actual value from the data instead (the lower middle one).

## 15.6 "In every ..." { #every }

"Customers who placed a shipped order in **every** month from January to April." Count the different months per
customer and compare with the number of months:

**Task:** List the customers with a shipped order in every month from January to April 2026.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT customer_id
    FROM orders
    WHERE status = 'shipped'
      AND order_date >= '2026-01-01' AND order_date < '2026-05-01'
    GROUP BY customer_id
    HAVING COUNT(DISTINCT SUBSTR(CAST(order_date AS TEXT), 1, 7)) = 4;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | customer_id |
    | --- |
    | 1 |
    <!-- /result -->

`COUNT(DISTINCT month)` is essential: Ana Silva has two January orders, and `COUNT(*) = 4` would be true for someone
with four orders in one month. The double `NOT EXISTS` form of "for all" is in [chapter 9](09-Self-Semi-and-Anti-Joins.md#practice) (question 9.6).

## 15.7 Bought together { #pairs }

"Which pairs of products appear in the same order most often?" A self join of `order_items` on `order_id`, with
`a.product_id < b.product_id` to count each pair once:

**Task:** List the pairs of products bought together in at least 2 orders, with how many orders, most first (ties by product ids).

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT a.product_id AS product_a, b.product_id AS product_b, COUNT(*) AS orders_together
    FROM order_items a
    JOIN order_items b
      ON b.order_id = a.order_id
     AND a.product_id < b.product_id
    GROUP BY a.product_id, b.product_id
    HAVING COUNT(*) >= 2
    ORDER BY orders_together DESC, product_a, product_b;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | product_a | product_b | orders_together |
    | --- | --- | --- |
    | 2 | 3 | 2 |
    | 2 | 4 | 2 |
    | 4 | 5 | 2 |
    <!-- /result -->

Three pairs were bought together twice: the notebook (2) with the fountain pen (3), in orders 105 and 117; the
notebook with the coffee mug (4), in 103 and 117; and the coffee mug with the tea kettle (5), in 109 and 115. Join to
`products` for names if the task wants them.

## 15.8 Recognising the pattern { #recognise }

| The question says | Pattern | Chapter |
| --- | --- | --- |
| "the Nth highest", "the second largest" | DENSE_RANK = N, or DISTINCT + OFFSET | 13, 15.1 |
| "top N per ...", "the best in each ..." | RANK / ROW_NUMBER in a CTE, filter outside | 13 |
| "the latest / first ... for each ..." | ROW_NUMBER ... ORDER BY date DESC, id DESC = 1 | 13 |
| "duplicates", "appears more than once" | GROUP BY ... HAVING COUNT(*) > 1 | 15.2 |
| "consecutive", "streak", "in a row" | DISTINCT, then date − ROW_NUMBER | 15.3 |
| "compared with the previous", "change", "growth" | LAG | 14 |
| "so far", "cumulative", "to date" | SUM OVER (ORDER BY ... ROWS ...) | 14 |
| "one column per ..." | SUM(CASE ...) per column | 15.4 |
| "never", "without any", "no ..." | NOT EXISTS | 9 |
| "every", "all of" | COUNT(DISTINCT) = total, or double NOT EXISTS | 15.6, 9 |
| "percentage of", "share of" | 100.0 * x / SUM(x) OVER () | 13 |
| "including those with none", "show zero" | LEFT JOIN + COALESCE, or a calendar grid | 8, 16 |

## Practice { #practice }

**15.1** The third-highest product price (a price level, ties counted once).

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT DISTINCT price AS third_highest
    FROM products
    ORDER BY price DESC
    LIMIT 1 OFFSET 2;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | third_highest |
    | --- |
    | 25.00 |
    <!-- /result -->

    The levels are 149.00, 32.00, 25.00, 24.50, ... The tea kettle and the monitor stand share 32.00, so the third
    level is 25.00.

**15.2** For each customer who logged in, their longest streak of consecutive login days. (Write it for PostgreSQL;
the SQLite version swaps the date arithmetic as in 15.3.)

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH days AS (SELECT DISTINCT customer_id, login_date FROM logins),
    numbered AS (
      SELECT customer_id,
             login_date - CAST(ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY login_date) AS INTEGER) AS island
      FROM days
    ),
    runs AS (
      SELECT customer_id, island, COUNT(*) AS days FROM numbered GROUP BY customer_id, island
    )
    SELECT customer_id, MAX(days) AS longest_streak
    FROM runs
    GROUP BY customer_id
    ORDER BY longest_streak DESC, customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | customer_id | longest_streak |
    | --- | --- |
    | 4 | 4 |
    | 1 | 3 |
    | 2 | 2 |
    | 6 | 1 |
    <!-- /result -->

    **Gaps and islands.** Number each customer's login days 1, 2, 3; a date minus its number stays the same for
    as long as the days are consecutive, and changes after a gap. That value (`island`) names one run, so
    `COUNT(*)` per island is the run's length and `MAX` picks the longest. `DISTINCT` first, or a repeated login
    would break the numbering.


**15.3** Pivot: for each department, the number of employees hired in each of 2023, 2024 and 2025, as three columns.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT department,
           SUM(CASE WHEN SUBSTR(CAST(hire_date AS TEXT), 1, 4) = '2023' THEN 1 ELSE 0 END) AS hired_2023,
           SUM(CASE WHEN SUBSTR(CAST(hire_date AS TEXT), 1, 4) = '2024' THEN 1 ELSE 0 END) AS hired_2024,
           SUM(CASE WHEN SUBSTR(CAST(hire_date AS TEXT), 1, 4) = '2025' THEN 1 ELSE 0 END) AS hired_2025
    FROM employees
    GROUP BY department
    ORDER BY department;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | department | hired_2023 | hired_2024 | hired_2025 |
    | --- | --- | --- | --- |
    | Engineering | 0 | 1 | 0 |
    | Management | 0 | 0 | 0 |
    | Sales | 2 | 0 | 1 |
    | Support | 0 | 1 | 0 |
    <!-- /result -->

    A **pivot**: one `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` per output column counts only the rows of that year.
    `GROUP BY department` gives one row per department; the years become columns instead of rows.


**15.4** Order ids are meant to run from 101 with no gaps. Check it: list any missing ids between the smallest and
largest. (There are none in the sample; prove it.)

??? success "Answer"
    Gaps are found where the next id is more than one above this one:

    <!-- sql -->
    ```sql
    WITH n AS (
      SELECT order_id, LEAD(order_id) OVER (ORDER BY order_id) AS next_id
      FROM orders
    )
    SELECT order_id + 1 AS gap_starts, next_id - 1 AS gap_ends
    FROM n
    WHERE next_id - order_id > 1;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

    | gap_starts | gap_ends |
    | --- | --- |
    | *(no rows)* | |
    <!-- /result -->

    No rows: no gaps. To be sure the check works, run it on a set with a hole, such as `orders` without order 110
    (`WHERE order_id <> 110` in the CTE); it reports 110 to 110.

**15.5** The median order value (all orders, by revenue per order). Use the portable window method.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH v AS (
      SELECT order_id, SUM(quantity * unit_price) AS total
      FROM order_items GROUP BY order_id
    ),
    r AS (
      SELECT total,
             ROW_NUMBER() OVER (ORDER BY total, order_id) AS rn,
             COUNT(*) OVER () AS n
      FROM v
    )
    SELECT AVG(total) AS median_order_value
    FROM r
    WHERE rn IN ((n + 1) / 2, (n + 2) / 2);
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | median_order_value |
    | --- |
    | 36.7500000000000000 |
    <!-- /result -->

    20 orders, so the median is the average of the 10th and 11th values in order.

**15.6** Customers who ordered (any status) in two consecutive calendar months at least once.

??? success "Answer"
    Turn each month into a number (`year * 12 + month`) so that consecutive months differ by exactly 1, then
    compare each customer's months with LAG:

    <!-- sql -->
    ```sql
    WITH m AS (
      SELECT DISTINCT customer_id,
             CAST(SUBSTR(CAST(order_date AS TEXT), 1, 4) AS INTEGER) * 12
               + CAST(SUBSTR(CAST(order_date AS TEXT), 6, 2) AS INTEGER) AS month_no
      FROM orders
      WHERE customer_id IS NOT NULL
    ),
    l AS (
      SELECT customer_id, month_no,
             LAG(month_no) OVER (PARTITION BY customer_id ORDER BY month_no) AS prev_month_no
      FROM m
    )
    SELECT DISTINCT customer_id
    FROM l
    WHERE month_no - prev_month_no = 1
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_id |
    | --- |
    | 1 |
    | 2 |
    | 6 |
    <!-- /result -->

**Next:** [16. Dates and time series](16-Dates-and-Time-Series.md).
