# 26. Making slow queries fast

*Two queries can return exactly the same rows and differ a thousand times in speed. This chapter times the common
rewrites on tables of 10,000 to 200,000 rows, on both databases, so you can see which forms grow gently with the
data and which explode. It also gives the habits that keep queries fast, and the order to try them in.*

!!! abstract "In this chapter"
    **You will learn:**

    - how to approach a slow query: measure, find the slow step, change one thing, check the answer
    - why a correlated subquery can run once per row, and the window or join that replaces it
    - why a self join on "earlier rows" grows with the square of the group size, and `LAG` does not
    - the anti-join forms (`NOT IN`, `NOT EXISTS`, `LEFT JOIN ... IS NULL`), and a SQLite trap
    - the greatest row per group, indexes for lookups, and `UNION` versus `UNION ALL`
    - smaller habits: fewer columns, aggregate before joining, sargable conditions

    **You need:** [chapter 10](10-Subqueries.md), [chapter 13](13-Window-Functions-Ranking.md),
    [chapter 14](14-Window-Functions-Lag-Lead-Running-Totals.md) and [chapter 25](25-Indexes-and-Explain.md).

## 26.1 How the timings were made { #method }

The tables on this page are made by `tools/sqltime.py`. For each comparison it builds the same tables in PostgreSQL
16 and SQLite 3.53 from a fixed random seed, runs `ANALYZE`, then runs every version of the query and checks that
**every version returns exactly the same rows** on both databases. A faster query that gives a different answer is
not an improvement. Each time is the median of three runs; a version still running after 30 seconds is stopped.
PostgreSQL runs without parallel workers, so both databases use one processor core.

The numbers will be different on your machine; **the ratios are the point**. A rewrite that is 2 times faster here
is about 2 times faster anywhere; one that is 500 times faster is the difference between a test passing and timing
out.

The method, for any slow query:

1. **Measure** it, on realistic data (`EXPLAIN ANALYZE`, or the platform's query profile).
2. **Find the step** that takes the time: a scan of a big table, a nested loop with many loops, a sort, a subplan
   run once per row ([chapter 25](25-Indexes-and-Explain.md#analyze)).
3. **Change one thing**: the query's form, an index, fresh statistics.
4. **Check the answer** is the same, then measure again.

## 26.2 Correlated subquery, window, or join { #correlated }

"Employees who earn more than their department's average." Three correct ways to write it, here on the shop's
twelve employees, giving the same five people:

=== "Correlated subquery"

    <!-- sql -->
    ```sql
    SELECT e.employee_id, e.name
    FROM employees e
    WHERE e.salary > (SELECT AVG(x.salary) FROM employees x
                      WHERE x.department = e.department)
    ORDER BY e.employee_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | employee_id | name |
    | --- | --- |
    | 2 | Tom Becker |
    | 3 | Priya Nair |
    | 4 | Sam Lee |
    | 6 | Omar Aziz |
    | 10 | Kwame Mensah |
    <!-- /result -->

=== "Window function"

    <!-- sql same -->
    ```sql
    SELECT employee_id, name
    FROM (SELECT employee_id, name, salary,
                 AVG(salary) OVER (PARTITION BY department) AS dept_avg
          FROM employees) t
    WHERE salary > dept_avg
    ORDER BY employee_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 5 rows.</p>

    | employee_id | name |
    | --- | --- |
    | 2 | Tom Becker |
    | 3 | Priya Nair |
    | 4 | Sam Lee |
    | 6 | Omar Aziz |
    | 10 | Kwame Mensah |
    <!-- /result -->

=== "Join to a grouped CTE"

    <!-- sql same -->
    ```sql
    WITH d AS (SELECT department, AVG(salary) AS dept_avg
               FROM employees GROUP BY department)
    SELECT e.employee_id, e.name
    FROM employees e
    JOIN d ON d.department = e.department
    WHERE e.salary > d.dept_avg
    ORDER BY e.employee_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 5 rows.</p>

    | employee_id | name |
    | --- | --- |
    | 2 | Tom Becker |
    | 3 | Priya Nair |
    | 4 | Sam Lee |
    | 6 | Omar Aziz |
    | 10 | Kwame Mensah |
    <!-- /result -->

The correlated subquery computes the department average **again for every employee**: with 10,000 employees in 10
departments, that is 10,000 averages over 1,000 rows each. The other two compute each average once. On a table
`big_emps (emp_id, dept_id, salary)` with random salaries:

<!-- timing above-average -->
<p class="sql-tested">Timed by <code>tools/sqltime.py</code> on 11 November 2026, one 2.3 GHz Xeon core per database, tables in memory or cache; the median of three runs. Every version that finished returned the same rows on both databases.</p>

| 10,000 employees, 10 departments (4,981 rows in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| correlated subquery | 2.2 s | 2.9 s |
| window function | 7 ms | 5 ms |
| join to a grouped CTE | 6 ms | 3 ms |

| 100,000 employees, 10 departments (49,770 rows in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| correlated subquery | stopped after 30 s | stopped after 30 s |
| window function | 58 ms | 63 ms |
| join to a grouped CTE | 36 ms | 41 ms |
<!-- /timing -->

Ten times more rows made the window and the join about ten times slower. The correlated subquery went from 2 to 3
seconds to more than 30, when it was stopped: its work grows with rows × rows per department, so ten times the
employees, each averaging ten times as many colleagues, means about a hundred times the work, several minutes.
Neither database remembers the average from one row to the next.

Does an index on the department rescue the correlated form? Only when the groups are small:

<!-- timing above-average-index -->
<p class="sql-tested">Timed by <code>tools/sqltime.py</code> on 11 November 2026, one 2.3 GHz Xeon core per database, tables in memory or cache; the median of three runs. Every version that finished returned the same rows on both databases.</p>

| 100,000 employees, 10 departments, index on dept_id (49,770 rows in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| correlated subquery | stopped after 30 s | stopped after 30 s |
| window function | 43 ms | 63 ms |
| join to a grouped CTE | 36 ms | 36 ms |

| 100,000 employees, 10,000 departments, index on dept_id (49,869 rows in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| correlated subquery | 667 ms | 376 ms |
| window function | 59 ms | 72 ms |
| join to a grouped CTE | 39 ms | 68 ms |
<!-- /timing -->

With 10 departments, each lookup still averages 10,000 rows, and the index does not help. With 10,000 departments
of about 10 employees, each lookup is tiny and the correlated subquery becomes usable, though still slower than
computing all averages in one pass. **Prefer the window or the join**: they are fast whatever the shape of the
data. A correlated `EXISTS` or `NOT EXISTS` on an indexed key is different: it stops at the first match and is
usually fine (but see [26.4](#anti-join) for SQLite).

## 26.3 Self join on earlier rows, or LAG { #lag }

"For each visit, the customer's previous visit day." The self-join form joins each visit to **all** of the same
customer's earlier visits and keeps the latest; `LAG` reads the one row before ([chapter 14](14-Window-Functions-Lag-Lead-Running-Totals.md#lag-lead)).

```sql
-- self join
SELECT a.visit_id, MAX(b.day) AS previous_day
FROM visits a
LEFT JOIN visits b ON b.customer_id = a.customer_id AND b.day < a.day
GROUP BY a.visit_id;

-- window
SELECT visit_id, LAG(day) OVER (PARTITION BY customer_id ORDER BY day) AS previous_day
FROM visits;
```

The same 100,000 visits, first spread as 10 per customer, then as 1,000 per customer:

<!-- timing previous-visit -->
<p class="sql-tested">Timed by <code>tools/sqltime.py</code> on 11 November 2026, one 2.3 GHz Xeon core per database, tables in memory or cache; the median of three runs. Every version that finished returned the same rows on both databases.</p>

| 100,000 visits, 10 per customer (100,000 rows in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| self join on earlier days | 170 ms | 111 ms |
| LAG window function | 72 ms | 70 ms |

| 100,000 visits, 1,000 per customer (100,000 rows in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| self join on earlier days | 5.1 s | 4.5 s |
| LAG window function | 61 ms | 84 ms |
<!-- /timing -->

The self join builds about n²/2 pairs per customer: 45 pairs for 10 visits, about 500,000 for 1,000 visits. Same
table size, very different cost, so a self join can pass a small test and time out on the large hidden one. `LAG`
sorts each customer's rows once. The same applies to "orders within 7 days of the previous one", running totals
written as a self join, and "days since the last event": use `LAG`, `LEAD` or a window frame.

## 26.4 Anti-joins: NOT IN, NOT EXISTS, LEFT JOIN ... IS NULL { #anti-join }

"Customers who never ordered", three ways ([chapter 9](09-Self-Semi-and-Anti-Joins.md#anti)). `NOT IN` is shown with
`WHERE customer_id IS NOT NULL` inside, because without it a single NULL makes `NOT IN` return no rows at all
([chapter 6](06-Null-and-Three-Valued-Logic.md#joins-not-in)); that correctness problem comes first.

```sql
SELECT customer_id FROM c
WHERE customer_id NOT IN (SELECT customer_id FROM o WHERE customer_id IS NOT NULL);

SELECT customer_id FROM c
WHERE NOT EXISTS (SELECT 1 FROM o WHERE o.customer_id = c.customer_id);

SELECT c.customer_id FROM c
LEFT JOIN o ON o.customer_id = c.customer_id
WHERE o.order_id IS NULL;
```

<!-- timing anti-join -->
<p class="sql-tested">Timed by <code>tools/sqltime.py</code> on 11 November 2026, one 2.3 GHz Xeon core per database, tables in memory or cache; the median of three runs. Every version that finished returned the same rows on both databases.</p>

| 50,000 customers, 200,000 orders, no index on o.customer_id (10,267 rows in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| NOT IN | 46 ms | 61 ms |
| NOT EXISTS | 33 ms | stopped after 30 s |
| LEFT JOIN ... IS NULL | 34 ms | 121 ms |

| the same, with an index on o.customer_id (10,267 rows in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| NOT IN | 44 ms | 17 ms |
| NOT EXISTS | 31 ms | 10 ms |
| LEFT JOIN ... IS NULL | 32 ms | 14 ms |

| the same, no index, PostgreSQL given only 64 kB of work_mem (10,267 rows in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| NOT IN | stopped after 30 s | 59 ms |
| NOT EXISTS | 35 ms | stopped after 30 s |
| LEFT JOIN ... IS NULL | 39 ms | 117 ms |
<!-- /timing -->

What the three groups show:

- **PostgreSQL** turns `NOT EXISTS` and `LEFT JOIN ... IS NULL` into the same plan, a hash anti join: fast, with or
  without an index. `NOT IN` is fast too while the subquery's result fits in memory (`work_mem`, 4 MB by default),
  because PostgreSQL then hashes it once. Given too little memory (the third group), it falls back to scanning the
  subquery's result again for each customer, and stops being usable. `NOT IN` cannot be turned into an anti join,
  because of how it treats NULLs.
- **SQLite** runs `NOT EXISTS` as written: for each customer, a search of `o`. **Without an index on
  `o.customer_id`, that is a full scan of 200,000 orders per customer, and it never finishes.** With the index it
  takes milliseconds. `LEFT JOIN` survives without an index because SQLite builds a temporary one by itself
  ("automatic index"); `NOT IN` builds a temporary table of the subquery's values.

So: on PostgreSQL, write `NOT EXISTS` or `LEFT JOIN ... IS NULL`. On SQLite, make sure the inner column is indexed,
or use `LEFT JOIN ... IS NULL`, which does not depend on it. In a test where you cannot add indexes, the
`LEFT JOIN` form is the safe one on both.

## 26.5 The greatest row per group { #top-per-group }

"Each customer's largest order amount." Three ways:

```sql
-- ROW_NUMBER, keep 1 (returns the whole row, not just the amount)
SELECT customer_id, amount FROM (
  SELECT customer_id, amount,
         ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY amount DESC, order_id) AS rn
  FROM o) t
WHERE rn = 1;

-- GROUP BY (only the grouped column and aggregates)
SELECT customer_id, MAX(amount) AS amount FROM o GROUP BY customer_id;

-- correlated
SELECT DISTINCT o.customer_id, o.amount FROM o
WHERE o.amount = (SELECT MAX(x.amount) FROM o x WHERE x.customer_id = o.customer_id);
```

<!-- timing top-per-group -->
<p class="sql-tested">Timed by <code>tools/sqltime.py</code> on 11 November 2026, one 2.3 GHz Xeon core per database, tables in memory or cache; the median of three runs. Every version that finished returned the same rows on both databases.</p>

| 50,000 customers, 200,000 orders (39,733 rows in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| ROW_NUMBER, keep 1 | 77 ms | 166 ms |
| GROUP BY MAX | 48 ms | 74 ms |
| correlated = (SELECT MAX ...) | stopped after 30 s | stopped after 30 s |
<!-- /timing -->

`GROUP BY MAX` is the fastest when you need only the maximum. `ROW_NUMBER` is close behind on PostgreSQL and about
twice as slow on SQLite, and it returns the whole row (the order id, the date), which is usually what a task asks
for. The correlated form is the slow one again.

For a single maximum over the whole table, `ORDER BY amount DESC LIMIT 1` and `MAX(amount)` both read every row
once without an index (PostgreSQL's top-N sort keeps only the best row while reading); with an index on the column,
both read one index entry ([chapter 25](25-Indexes-and-Explain.md#order-limit)).

## 26.6 An index for a lookup { #index }

Finding one customer's orders in 200,000 rows:

<!-- timing index-lookup -->
<p class="sql-tested">Timed by <code>tools/sqltime.py</code> on 11 November 2026, one 2.3 GHz Xeon core per database, tables in memory or cache; the median of three runs. Every version that finished returned the same rows on both databases.</p>

| 50,000 customers, 200,000 orders (2 rows in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| no index | 7 ms | 5 ms |
| with an index on customer_id | under 1 ms | under 1 ms |
<!-- /timing -->

A scan of 200,000 rows takes only a few milliseconds, which is why small tests never show the problem. The index
lookup took under a millisecond. The gap grows with the table: a scan's time grows with the number of rows, while
an index lookup only needs a few more page reads as the tree gets deeper. When a query runs many times (a
dashboard, an API, the inner side of a nested loop), this is the difference that matters.

## 26.7 UNION or UNION ALL { #union }

`UNION` removes duplicates, which means sorting or hashing the whole combined result; `UNION ALL` just appends.
When the parts cannot overlap (here, orders split by amount), both return the same rows:

<!-- timing union -->
<p class="sql-tested">Timed by <code>tools/sqltime.py</code> on 11 November 2026, one 2.3 GHz Xeon core per database, tables in memory or cache; the median of three runs. Every version that finished returned the same rows on both databases.</p>

| 200,000 orders split in two halves (1 row in the answer) | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| UNION | 82 ms | 27 ms |
| UNION ALL | 21 ms | 14 ms |
<!-- /timing -->

Use `UNION ALL` unless you need duplicates removed ([chapter 12](12-Set-Operations.md#union)).

## 26.8 Smaller habits { #habits }

- **Select only the columns you need.** `SELECT *` reads and sends every column, defeats covering indexes, and in
  columnar warehouses reads columns from disk that the query never uses.
- **Aggregate before joining** when a join would multiply rows ([chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md#fan-out)).
  Summing order lines per order first, then joining to orders, is both correct and smaller than joining everything
  and summing at the end. A `DISTINCT` added to "fix" duplicates from a join usually hides this mistake at a cost.
- **Keep conditions sargable**: no function or calculation on an indexed column ([chapter 25](25-Indexes-and-Explain.md#sargable)).
  A `LIKE '%text'` that starts with a wildcard cannot use a B-tree index at all; searching inside text needs a
  full-text or trigram index.
- **Filter early.** Put conditions in `WHERE`, not in `HAVING`, when they do not depend on an aggregate, so rows are
  dropped before grouping. The planner moves many filters for you, but not across every `GROUP BY`, window or
  `DISTINCT`.
- **Use `EXISTS` for "is there at least one"**, not `COUNT(*) > 0`: `EXISTS` can stop at the first row.
- **Keep statistics fresh** after big loads (`ANALYZE`), so the planner's row estimates are right.
- **CTEs are not automatically cached.** PostgreSQL 12 and later fold a CTE used once into the main query; one used
  several times is computed once and stored. `WITH x AS MATERIALIZED (...)` or `NOT MATERIALIZED` overrides that.
  Other databases differ; do not assume a CTE is computed only once.

## 26.9 Summary { #summary }

- Measure, find the slow step, change one thing, check the answer, measure again.
- A correlated subquery that aggregates can run once per row: replace it with a window function or a join to a
  grouped CTE (here, under 100 ms against more than 30 s).
- A self join on "earlier rows" grows with the square of the rows per key: use `LAG`, `LEAD` or a frame.
- Anti-join: `NOT EXISTS` or `LEFT JOIN ... IS NULL` on PostgreSQL; on SQLite `NOT EXISTS` needs an index on the
  inner column, `LEFT JOIN` does not. `NOT IN` is fragile with NULLs and with large subqueries.
- Greatest per group: `GROUP BY MAX` for the value, `ROW_NUMBER` for the whole row; never the correlated form.
- Index columns you look up often; `UNION ALL` unless you need duplicates removed; fewer columns; aggregate before
  joining.

!!! question "Asked aloud: performance"
    ??? note "A query is slow. Walk me through what you do."
        Reproduce it on realistic data and get the plan with actual timings (`EXPLAIN ANALYZE` or the query profile).
        Find the expensive step and compare estimated with actual rows. Then fix the cause: missing or unusable index,
        stale statistics, a correlated subquery or self join that runs per row, a join that multiplies rows, reading far
        more columns or partitions than needed. Change one thing at a time, check the result is identical, and measure
        again.

    ??? note "Why can a correlated subquery be slow, and what do you replace it with?"
        It refers to the outer row, so the database may run it once per outer row; if it aggregates a group each time,
        the work is rows × group size. Replace it with a window function over the group, or compute the per-group values
        once in a CTE and join to them. Correlated `EXISTS` on an indexed key is usually fine, because it stops at the
        first match.

    ??? note "NOT IN, NOT EXISTS or LEFT JOIN IS NULL?"
        For correctness, avoid `NOT IN` on a column that can be NULL: one NULL makes it return nothing. For speed,
        PostgreSQL plans `NOT EXISTS` and `LEFT JOIN ... IS NULL` identically as an anti join; `NOT IN` cannot be
        planned that way and degrades when the subquery result is large. On SQLite, `NOT EXISTS` runs per row and needs
        an index on the inner column.

    ??? note "UNION or UNION ALL?"
        `UNION ALL` appends results; `UNION` also removes duplicates, which costs a sort or hash of everything. Use
        `UNION ALL` unless duplicates are possible and must go.

    ??? note "How do you make a query faster in a data warehouse?"
        Read less: select only needed columns, filter on partition or clustering columns so files are skipped, avoid
        functions on those columns, aggregate before joining, and avoid exploding joins. Check the profile for spilled
        joins or skewed partitions. Materialize expensive repeated results as tables or materialized views.

    ??? note "Why might the same query be fast in the test and slow in production?"
        Data size and shape: a form that grows with the square of group size (a self join, a correlated subquery) is
        quick on small data. Also different statistics, missing indexes, more concurrent load, different settings
        (memory for hashing and sorting), or a parameter value that matches far more rows than the one tested.

## Practice { #practice }

**26.1** Rewrite without a correlated subquery, so that it scales: the products whose price is above the average
price of their category.

```sql
SELECT p.product_id, p.name
FROM products p
WHERE p.price > (SELECT AVG(x.price) FROM products x WHERE x.category = p.category);
```

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT product_id, name
    FROM (SELECT product_id, name, price,
                 AVG(price) OVER (PARTITION BY category) AS cat_avg
          FROM products) t
    WHERE price > cat_avg
    ORDER BY product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | product_id | name |
    | --- | --- |
    | 1 | Desk lamp |
    | 5 | Tea kettle |
    | 6 | Office chair |
    | 9 | Wall clock |
    <!-- /result -->

    Products with no category: in the original, `x.category = p.category` is never true for NULL, so the average is
    NULL and the product is left out. In the window version, the NULL-category products form their own partition
    (the gift card alone), and its price is not above its own average, so it is also left out. Same rows; check this
    kind of NULL detail whenever you rewrite.

**26.2** Rewrite with `LAG`: for each of customer 1's orders, the number of days since their previous order, using
this self join.

```sql
SELECT a.order_id, a.order_date, MAX(b.order_date) AS previous_date
FROM orders a
LEFT JOIN orders b ON b.customer_id = a.customer_id AND b.order_date < a.order_date
WHERE a.customer_id = 1
GROUP BY a.order_id, a.order_date
ORDER BY a.order_date;
```

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT order_id, order_date,
           LAG(order_date) OVER (ORDER BY order_date, order_id) AS previous_date
    FROM orders
    WHERE customer_id = 1
    ORDER BY order_date, order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | order_id | order_date | previous_date |
    | --- | --- | --- |
    | 101 | 2026-01-03 | *NULL* |
    | 103 | 2026-01-15 | 2026-01-03 |
    | 110 | 2026-02-20 | 2026-01-15 |
    | 115 | 2026-03-18 | 2026-02-20 |
    | 120 | 2026-04-05 | 2026-03-18 |
    <!-- /result -->

    The days between them is `order_date - previous_date` on PostgreSQL and
    `julianday(order_date) - julianday(previous_date)` on SQLite ([chapter 16](16-Dates-and-Time-Series.md#arithmetic)).
    If a customer could order twice on one day, the two forms differ: the self join's `<` skips the same-day order,
    `LAG` does not. Decide which the task means.

**26.3** A colleague's test passes on 100 rows and times out on the hidden test with 1,000,000. The query finds,
for each order, the number of earlier orders by the same customer, with a self join and `COUNT`. What do you
suggest?

??? success "Answer"
    `ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) - 1`. The self join pairs every order
    with every earlier one of the same customer, so its work grows with the square of each customer's order count;
    the window sorts each customer's orders once. If equal dates must count as "not earlier", use `RANK()` minus 1
    with `ORDER BY order_date` instead.

**26.4** On SQLite, `SELECT ... FROM c WHERE NOT EXISTS (SELECT 1 FROM o WHERE o.customer_id = c.customer_id)` never
finishes on a large table. Give two fixes.

??? success "Answer"
    Create an index on `o (customer_id)`, so each check is a quick search; or rewrite as
    `LEFT JOIN o ON o.customer_id = c.customer_id WHERE o.customer_id IS NULL`, for which SQLite builds a temporary
    index by itself ([26.4](#anti-join)).

**Next:** [27. GROUPING SETS, ROLLUP, CUBE and LATERAL](27-Grouping-Sets-Rollup-Cube-Lateral.md).
